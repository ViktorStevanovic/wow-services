import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.enums import Region
from app.core.security import (
    OAuthState,
    OAuthStateSigner,
    TokenCipher,
    generate_token,
    hash_token,
)
from app.features.auth.exceptions import (
    BattlenetLoginCancelledError,
    DevAccountNotFoundError,
    DevLoginUnavailableError,
    OAuthStateError,
    RegionNotSupportedError,
)
from app.features.auth.models import UserSession
from app.features.auth.schemas import AuthenticatedUser, DevAccountRead, LoginRedirect, LoginResult
from app.features.users.enums import UserStatus
from app.features.users.exceptions import AccountSuspendedError
from app.features.users.models import User
from app.features.users.service import UserService
from app.integrations.blizzard.exceptions import BlizzardAuthError
from app.integrations.blizzard.mock import MockBlizzardProvider
from app.integrations.blizzard.provider import BlizzardProvider


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: BlizzardProvider,
        users: UserService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider
        self._users = users
        self._signer = OAuthStateSigner(settings.session_secret)
        self._cipher = TokenCipher(settings.token_encryption_key)

    # --- Sign-in ------------------------------------------------------------------------

    def start_login(self, region: Region) -> LoginRedirect:
        state = self._new_state(region)
        url = self._provider.build_authorize_url(region, state.state)
        return LoginRedirect(url=url, signed_state=self._signer.dumps(state))

    async def complete_login(
        self,
        *,
        signed_state: str | None,
        state: str | None,
        code: str | None,
        error: str | None,
        previous_session_token: str | None = None,
    ) -> LoginResult:
        """Battle.net callback: verify state, exchange the code, upsert the user, open a session."""
        expected = self._signer.loads(signed_state) if signed_state else None
        if expected is None or not state or not secrets.compare_digest(expected.state, state):
            raise OAuthStateError()
        if error:
            raise BattlenetLoginCancelledError()
        if not code:
            raise BlizzardAuthError()

        token = await self._provider.exchange_code(expected.region, code)
        account = await self._provider.fetch_account(token)
        now = datetime.now(UTC)
        user = await self._users.upsert_from_battlenet(expected.region, account, now)
        if user.status is UserStatus.SUSPENDED:
            raise AccountSuspendedError()
        # Step 4: import the account's characters here.

        if previous_session_token:
            await self._delete_session(previous_session_token)
        session_token = generate_token()
        self._session.add(
            UserSession(
                token_hash=hash_token(session_token),
                user_id=user.id,
                blizzard_token_encrypted=self._cipher.encrypt(
                    token.access_token.get_secret_value()
                ),
                blizzard_token_expires_at=token.expires_at,
                expires_at=now + timedelta(days=self._settings.session_lifetime_days),
            )
        )
        await self._session.commit()
        return LoginResult(session_token=session_token, redirect_url=self._settings.frontend_url)

    # --- Dev login (mock mode only) -----------------------------------------------------

    def list_dev_accounts(self) -> list[DevAccountRead]:
        return [
            DevAccountRead(
                key=account.key,
                region=account.region,
                battletag=account.battletag,
                character_names=[f"{c.first_name} {c.last_name}" for c in account.characters],
            )
            for account in self._mock_provider().accounts
        ]

    def start_dev_login(self, account_key: str) -> LoginRedirect:
        mock = self._mock_provider()
        account = next((a for a in mock.accounts if a.key == account_key), None)
        if account is None:
            raise DevAccountNotFoundError(details={"account": account_key})
        state = self._new_state(account.region)
        url = mock.authorize_url_for(account.key, state.state)
        return LoginRedirect(url=url, signed_state=self._signer.dumps(state))

    # --- Sessions -----------------------------------------------------------------------

    async def authenticate(self, session_token: str | None) -> AuthenticatedUser | None:
        """The user behind a session cookie, or None if absent, unknown or expired."""
        if not session_token:
            return None
        row = (
            await self._session.exec(
                select(UserSession, User)
                .join(User, col(User.id) == col(UserSession.user_id))
                .where(
                    UserSession.token_hash == hash_token(session_token),
                    col(UserSession.expires_at) > func.now(),
                )
            )
        ).first()
        if row is None:
            return None
        user_session, user = row
        if user.status is UserStatus.SUSPENDED:
            raise AccountSuspendedError()
        return AuthenticatedUser(
            id=user.id, region=user.region, status=user.status, session_id=user_session.id
        )

    async def logout(self, session_token: str | None) -> None:
        if session_token:
            await self._delete_session(session_token)
            await self._session.commit()

    # --- Helpers ------------------------------------------------------------------------

    def _new_state(self, region: Region) -> OAuthState:
        if region not in self._settings.blizzard_regions:
            raise RegionNotSupportedError(details={"region": region.value})
        return OAuthState(state=generate_token(), region=region)

    def _mock_provider(self) -> MockBlizzardProvider:
        if not isinstance(self._provider, MockBlizzardProvider):
            raise DevLoginUnavailableError()
        return self._provider

    async def _delete_session(self, session_token: str) -> None:
        await self._session.exec(
            delete(UserSession).where(col(UserSession.token_hash) == hash_token(session_token))
        )

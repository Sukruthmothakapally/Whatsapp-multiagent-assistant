from google_auth_oauthlib.flow import Flow
import pickle
from typing import Dict, Any

from server.config import google_settings


class GoogleAuthHandler:
    """Utility class for handling Google authentication"""
    
    @staticmethod
    def create_auth_flow() -> Flow:
        """Create Google OAuth flow"""
        return Flow.from_client_secrets_file(
            google_settings.client_secrets_file,
            scopes=google_settings.scopes,
            redirect_uri=google_settings.redirect_uri
        )
    
    @classmethod
    def get_auth_url(cls) -> str:
        """Get authorization URL for OAuth flow"""
        flow = cls.create_auth_flow()
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline',
            include_granted_scopes='true'
        )
        return auth_url
    
    @classmethod
    def fetch_and_save_token(cls, auth_response: str) -> Dict[str, Any]:
        """Fetch OAuth token and save to file"""
        flow = cls.create_auth_flow()
        flow.fetch_token(authorization_response=auth_response)
        
        # Save credentials to file
        credentials = flow.credentials
        with open(google_settings.token_file, "wb") as f:
            pickle.dump(credentials, f)
        
        return {
            "token_expiry": str(credentials.expiry),
            "scopes": credentials.scopes
        }


google_auth = GoogleAuthHandler()
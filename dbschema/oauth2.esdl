module oauth2 {
    scalar type GrantType extending enum<authorization_code, password, client_credentials, refresh_token>;
    scalar type ResponseType extending enum<token, code>;
    scalar type CodeChallengeMethod extending enum<plain, S256>;
    
    type AuthorizationCode {
        required property code -> str;
        required link client -> Client;
        required property redirect_uri -> str;
        required property response_type -> ResponseType;
        required property scope -> str;
        required property auth_time -> int64;
        property code_challenge -> str;
        property code_challenge_method -> CodeChallengeMethod;
        property nonce -> str;
    }

    type Client {
        required property client_secret -> str;
        property grant_types -> array<GrantType>;
        property response_types -> array<ResponseType>;
        property redirect_uris -> array<str>;
        property scope -> str;
        property client_id := (<str>__source__.id);
    }

    type Token {
        required link user -> default::User;
        required property access_token -> str;
        required property refresh_token -> str;
        required property scope -> str;
        required property issued_at -> int64;
        required property expires_in -> int64;
        required link client -> Client;
        property token_type -> str;
        property revoked -> bool;
    }
};

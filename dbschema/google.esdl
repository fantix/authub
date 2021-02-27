module google {
    type GoogleIdP extending base::IdentityProvider {
        required property client_id -> str;
        required property client_secret -> str;
    }
};

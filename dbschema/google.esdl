module google {
    type Provider extending default::IdentityProvider {
        required property client_id -> str;
        required property client_secret -> str;
    }
};

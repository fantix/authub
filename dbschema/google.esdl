module google {
    type Client extending default::IdPClient {
        required property client_id -> str;
        required property client_secret -> str;
    }

    type Identity extending default::Identity {
        required property email -> str;
    }
};

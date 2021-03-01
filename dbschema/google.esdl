module google {
    type Client extending default::IdPClient {
        required property client_id -> str;
        required property client_secret -> str;
    }
};

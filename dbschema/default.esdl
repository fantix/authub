module default {
    type IdPClient {
        required property name -> str;
    }

    type Identity {
        required link user -> User;
        required link client -> IdPClient;
    }

    type User {
    }
};

module google {
    type Client extending default::IdPClient {
        required property client_id -> str;
        required property client_secret -> str;
    }

    type Identity extending default::Identity {
        required property iss -> str;
        required property azp -> str;
        required property aud -> str;
        required property sub -> str;
        required property hd -> str;
        required property email -> str;
        required property email_verified -> bool;
        required property at_hash -> str;
        required property name -> str;
        required property picture -> str;
        required property given_name -> str;
        required property family_name -> str;
        required property locale -> str;
        required property iat -> int64;
        required property exp -> int64;
        required property access_token -> str;
        required property expires_in -> int64;
        required property scope -> str;
        required property token_type -> str;
        required property id_token -> str;
        required property expires_at -> int64;
        property iss_sub {
            USING ((.iss, .sub));
            constraint exclusive;
        };
        constraint exclusive on ((.iss, .sub));
    }
};

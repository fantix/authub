module github {
    type Client extending default::IdPClient {
        required property client_id -> str;
        required property client_secret -> str;
    }

    type Identity extending default::Identity {
        required property login -> str;
        required property github_id -> int64 {
            constraint exclusive;
        };
        required property node_id -> str;
        required property avatar_url -> str;
        required property gravatar_id -> str;
        required property url -> str;
        required property html_url -> str;
        required property followers_url -> str;
        required property following_url -> str;
        required property gists_url -> str;
        required property starred_url -> str;
        required property subscriptions_url -> str;
        required property organizations_url -> str;
        required property repos_url -> str;
        required property events_url -> str;
        required property received_events_url -> str;
        required property type -> str;
        required property site_admin -> bool;
        required property name -> str;
        required property company -> str;
        required property blog -> str;
        required property location -> str;
        required property email -> str;
        required property hireable -> bool;
        required property bio -> str;
        required property twitter_username -> str;
        required property public_repos -> int64;
        required property public_gists -> int64;
        required property followers -> int64;
        required property following -> int64;
        required property created_at -> str;
        required property updated_at -> str;
        required property access_token -> str;
        required property token_type -> str;
        required property scope -> str;
    }
};

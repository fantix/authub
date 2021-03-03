CREATE MIGRATION m1uifbyxta2ocvby4gsgz67tiq56jx4kaed6twxgorfwy6umkl6vhq
    ONTO m1f5ym27j7l6gafjo2w7eaoqmx3rvblk2dpuozzh3gvluky7iocqja
{
  CREATE MODULE github IF NOT EXISTS;
  CREATE TYPE github::Client EXTENDING default::IdPClient {
      CREATE REQUIRED PROPERTY client_id -> std::str;
      CREATE REQUIRED PROPERTY client_secret -> std::str;
  };
  CREATE TYPE github::Identity EXTENDING default::Identity {
      CREATE REQUIRED PROPERTY github_id -> std::int64;
      CREATE CONSTRAINT std::exclusive ON (.github_id);
      CREATE REQUIRED PROPERTY access_token -> std::str;
      CREATE REQUIRED PROPERTY avatar_url -> std::str;
      CREATE REQUIRED PROPERTY bio -> std::str;
      CREATE REQUIRED PROPERTY blog -> std::str;
      CREATE REQUIRED PROPERTY company -> std::str;
      CREATE REQUIRED PROPERTY created_at -> std::str;
      CREATE REQUIRED PROPERTY email -> std::str;
      CREATE REQUIRED PROPERTY events_url -> std::str;
      CREATE REQUIRED PROPERTY followers -> std::int64;
      CREATE REQUIRED PROPERTY followers_url -> std::str;
      CREATE REQUIRED PROPERTY following -> std::int64;
      CREATE REQUIRED PROPERTY following_url -> std::str;
      CREATE REQUIRED PROPERTY gists_url -> std::str;
      CREATE REQUIRED PROPERTY gravatar_id -> std::str;
      CREATE REQUIRED PROPERTY hireable -> std::bool;
      CREATE REQUIRED PROPERTY html_url -> std::str;
      CREATE REQUIRED PROPERTY location -> std::str;
      CREATE REQUIRED PROPERTY login -> std::str;
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY node_id -> std::str;
      CREATE REQUIRED PROPERTY organizations_url -> std::str;
      CREATE REQUIRED PROPERTY public_gists -> std::int64;
      CREATE REQUIRED PROPERTY public_repos -> std::int64;
      CREATE REQUIRED PROPERTY received_events_url -> std::str;
      CREATE REQUIRED PROPERTY repos_url -> std::str;
      CREATE REQUIRED PROPERTY scope -> std::str;
      CREATE REQUIRED PROPERTY site_admin -> std::bool;
      CREATE REQUIRED PROPERTY starred_url -> std::str;
      CREATE REQUIRED PROPERTY subscriptions_url -> std::str;
      CREATE REQUIRED PROPERTY token_type -> std::str;
      CREATE REQUIRED PROPERTY twitter_username -> std::str;
      CREATE REQUIRED PROPERTY type -> std::str;
      CREATE REQUIRED PROPERTY updated_at -> std::str;
      CREATE REQUIRED PROPERTY url -> std::str;
  };
};

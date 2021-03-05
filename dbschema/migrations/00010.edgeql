CREATE MIGRATION m15c2j7k74kjzzs7sdcodoxs3zwfmw3rmmqpwcfgcy4gmenofaq6la
    ONTO m1rt664x2o3ls3d56ps5pan7mz75u5gizczer2rmd4pb7evow3pfja
{
  CREATE MODULE oauth2 IF NOT EXISTS;
  CREATE FINAL SCALAR TYPE oauth2::GrantType EXTENDING enum<authorization_code, password, client_credentials, refresh_token>;
  CREATE FINAL SCALAR TYPE oauth2::ResponseType EXTENDING enum<token, code>;
  CREATE TYPE oauth2::Client {
      CREATE PROPERTY grant_types -> array<oauth2::GrantType>;
      CREATE PROPERTY response_types -> array<oauth2::ResponseType>;
      CREATE PROPERTY client_id := (<std::str>__source__.id);
      CREATE REQUIRED PROPERTY client_secret -> std::str;
      CREATE PROPERTY redirect_uris -> array<std::str>;
      CREATE PROPERTY scope -> std::str;
  };
  CREATE FINAL SCALAR TYPE oauth2::CodeChallengeMethod EXTENDING enum<plain, S256>;
  CREATE TYPE oauth2::AuthorizationCode {
      CREATE REQUIRED LINK client -> oauth2::Client;
      CREATE REQUIRED PROPERTY auth_time -> std::int64;
      CREATE REQUIRED PROPERTY code -> std::str;
      CREATE PROPERTY code_challenge -> std::str;
      CREATE PROPERTY code_challenge_method -> oauth2::CodeChallengeMethod;
      CREATE PROPERTY nonce -> std::str;
      CREATE REQUIRED PROPERTY redirect_uri -> std::str;
      CREATE REQUIRED PROPERTY response_type -> oauth2::ResponseType;
      CREATE REQUIRED PROPERTY scope -> std::str;
  };
  CREATE TYPE oauth2::Token {
      CREATE REQUIRED LINK client -> oauth2::Client;
      CREATE REQUIRED LINK user -> default::User;
      CREATE REQUIRED PROPERTY access_token -> std::str;
      CREATE REQUIRED PROPERTY expires_in -> std::int64;
      CREATE REQUIRED PROPERTY issued_at -> std::int64;
      CREATE REQUIRED PROPERTY refresh_token -> std::str;
      CREATE PROPERTY revoked -> std::bool;
      CREATE REQUIRED PROPERTY scope -> std::str;
      CREATE PROPERTY token_type -> std::str;
  };
};

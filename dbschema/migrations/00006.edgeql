CREATE MIGRATION m14plgwo35sxbxb55owvghvwk66abboeqygus7rilo7x6ojssmw2qq
    ONTO m1knsh27d37zgsldmuj3uaheac7v5rprgtmdyelmzsowyofepuig2a
{
  ALTER TYPE google::Identity {
      CREATE REQUIRED PROPERTY iss -> std::str;
      CREATE REQUIRED PROPERTY sub -> std::str;
      CREATE CONSTRAINT std::exclusive ON ((.iss, .sub));
      CREATE REQUIRED PROPERTY access_token -> std::str;
      CREATE REQUIRED PROPERTY at_hash -> std::str;
      CREATE REQUIRED PROPERTY aud -> std::str;
      CREATE REQUIRED PROPERTY azp -> std::str;
      CREATE REQUIRED PROPERTY email_verified -> std::bool;
      CREATE REQUIRED PROPERTY exp -> std::int64;
      CREATE REQUIRED PROPERTY expires_at -> std::int64;
      CREATE REQUIRED PROPERTY expires_in -> std::int64;
      CREATE REQUIRED PROPERTY family_name -> std::str;
      CREATE REQUIRED PROPERTY given_name -> std::str;
      CREATE REQUIRED PROPERTY hd -> std::str;
      CREATE REQUIRED PROPERTY iat -> std::int64;
      CREATE REQUIRED PROPERTY id_token -> std::str;
  };
  ALTER TYPE google::Identity {
      CREATE PROPERTY iss_sub {
          USING ((.iss, .sub));
          CREATE CONSTRAINT std::exclusive;
      };
      CREATE REQUIRED PROPERTY locale -> std::str;
      CREATE REQUIRED PROPERTY name -> std::str;
      CREATE REQUIRED PROPERTY picture -> std::str;
      CREATE REQUIRED PROPERTY scope -> std::str;
      CREATE REQUIRED PROPERTY token_type -> std::str;
  };
};

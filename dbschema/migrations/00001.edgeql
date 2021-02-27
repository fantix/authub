CREATE MIGRATION m17aygvczqo2v35a73ek5ze4pru3nfsa7yamzropkknozcedjgdfrq
    ONTO initial
{
  CREATE MODULE base IF NOT EXISTS;
  CREATE MODULE google IF NOT EXISTS;
  CREATE TYPE base::IdentityProvider {
      CREATE REQUIRED PROPERTY name -> std::str;
  };
  CREATE TYPE google::GoogleIdP EXTENDING base::IdentityProvider {
      CREATE REQUIRED PROPERTY client_id -> std::str;
      CREATE REQUIRED PROPERTY client_secret -> std::str;
  };
};

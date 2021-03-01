CREATE MIGRATION m1knsh27d37zgsldmuj3uaheac7v5rprgtmdyelmzsowyofepuig2a
    ONTO m1gf24nk4eur5lxtpyuwtqp6suut42k5w2snj2v7gwgjqwvlnzy7qa
{
  CREATE TYPE default::User;
  CREATE TYPE default::Identity {
      CREATE REQUIRED LINK client -> default::IdPClient;
      CREATE REQUIRED LINK user -> default::User;
  };
  CREATE TYPE google::Identity EXTENDING default::Identity {
      CREATE REQUIRED PROPERTY email -> std::str;
  };
};

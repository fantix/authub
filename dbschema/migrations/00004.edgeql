CREATE MIGRATION m1gf24nk4eur5lxtpyuwtqp6suut42k5w2snj2v7gwgjqwvlnzy7qa
    ONTO m1bod3ppnkht7wlgh26fzcqlomixdqjmiem4x7ftcyfop4f2m4yhka
{
  ALTER TYPE default::IdentityProvider RENAME TO default::IdPClient;
  ALTER TYPE google::Provider RENAME TO google::Client;
};

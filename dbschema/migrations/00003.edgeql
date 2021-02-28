CREATE MIGRATION m1bod3ppnkht7wlgh26fzcqlomixdqjmiem4x7ftcyfop4f2m4yhka
    ONTO m1jffl3ptds3rnwf2rnage6kwvvzfga2zqtvbxigugdebhji7hjeoa
{
  ALTER TYPE base::IdentityProvider RENAME TO default::IdentityProvider;
  DROP MODULE base;
};

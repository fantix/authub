CREATE MIGRATION m1rt664x2o3ls3d56ps5pan7mz75u5gizczer2rmd4pb7evow3pfja
    ONTO m1uifbyxta2ocvby4gsgz67tiq56jx4kaed6twxgorfwy6umkl6vhq
{
  ALTER TYPE github::Identity {
      DROP CONSTRAINT std::exclusive ON (.github_id);
      ALTER PROPERTY github_id {
          CREATE CONSTRAINT std::exclusive;
      };
  };
};

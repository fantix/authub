CREATE MIGRATION m1f5ym27j7l6gafjo2w7eaoqmx3rvblk2dpuozzh3gvluky7iocqja
    ONTO m14plgwo35sxbxb55owvghvwk66abboeqygus7rilo7x6ojssmw2qq
{
  ALTER TYPE default::User {
      CREATE PROPERTY email -> std::str;
      CREATE PROPERTY name -> std::str;
  };
};

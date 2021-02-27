# Authub

The hub software for user authentication.


## Dependencies

1. [EdgeDB Beta 1 or above](https://www.edgedb.com/docs/tutorial/install)
2. Python 3.9
3. [Poetry](https://python-poetry.org/docs/#installation)


## Getting Started

0. Create an EdgeDB instance, assuming the instance name is "authub".
1. Clone the repository and work from that directory for following steps.
2. Install Authub with the `standalone` extra dependencies:

   ```shell
   $ poetry install --extras standalone
   ```

3. Bring the EdgeDB schema to the latest:

   ```shell
   $ edgedb -I authub migrate
   ```

4. Run the development server:

   ```shell
   $ authub dev
   ```

5. Visit http://localhost:8000/docs for the interactive API documentation.


## Development

When the data models written in Python are changed, run the following:

1. Compile the models and update the EdgeDB SDL `*.esdl` files:

   ```shell
   $ authub compile-schema
   ```

2. Generate a new EdgeDB migration revision:

   ```shell
   $ edgedb -I authub create-migration
   ```

3. Verify the generated DDL `*.edgeql` file, add it to version control.
4. Run the migration again:

   ```shell
   $ edgedb -I authub migrate
   ```

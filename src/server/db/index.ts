import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";

import * as schema from "./schema";

const connectionString =
  process.env.DATABASE_URL?.replace("file:", "") ?? "./data/jobhunt.db";

const globalForDb = globalThis as unknown as {
  sqliteConnection: Database.Database | undefined;
};

function createConnection(): Database.Database {
  const db = new Database(connectionString);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  return db;
}

const sqlite = globalForDb.sqliteConnection ?? createConnection();

if (process.env.NODE_ENV !== "production") {
  globalForDb.sqliteConnection = sqlite;
}

export const db = drizzle(sqlite, { schema });
export { sqlite };

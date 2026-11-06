import { readFile } from "node:fs/promises";
import path from "node:path";

const CREDENTIALS_PATH = path.resolve("config/google_client_secret.json");
const TOKEN_PATH = path.resolve("config/google_token.json");

const SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"];

export type GmailResponse = {
  from: string;
  subject: string;
  snippet: string;
  date: string;
};

async function getGmail() {
  const { google } = await import("googleapis");
  const { OAuth2 } = google.auth;

  const credentialsFile = await readFile(CREDENTIALS_PATH, "utf8");
  const credentials = JSON.parse(credentialsFile);
  const { client_secret, client_id } = credentials.installed ?? credentials.web;

  const tokenFile = await readFile(TOKEN_PATH, "utf8");
  const token = JSON.parse(tokenFile);

  const client = new OAuth2({ clientId: client_id, clientSecret: client_secret });
  client.setCredentials({
    access_token: token.access_token,
    refresh_token: token.refresh_token,
  });

  return google.gmail({ version: "v1", auth: client });
}

export async function scanResponses(
  maxResults = 20,
): Promise<GmailResponse[]> {
  const gmail = await getGmail();

  const list = await gmail.users.messages.list({
    userId: "me",
    q: "in:inbox newer_than:7d (application OR bewerbung OR \"your application\" OR \"we received\") -unsubscribe category:promotions",
    maxResults,
  });

  const messages = list.data.messages ?? [];
  if (messages.length === 0) return [];

  const responses: GmailResponse[] = [];
  for (const message of messages.slice(0, 10)) {
    const full = await gmail.users.messages.get({
      userId: "me",
      id: message.id ?? "",
      format: "metadata",
      metadataHeaders: ["From", "Subject", "Date"],
    });

    const headers = full.data.payload?.headers ?? [];
    const header = (name: string) =>
      headers.find((entry) => entry.name?.toLowerCase() === name)?.value ?? "";

    responses.push({
      from: header("From"),
      subject: header("Subject"),
      snippet: full.data.snippet ?? "",
      date: header("Date"),
    });
  }
  return responses;
}

"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { updateDraftAction } from "../actions";

const STATUS_OPTIONS = ["draft", "sent", "replied", "bounced"] as const;

export function DraftEditor({
  draft,
}: {
  draft: {
    id: number;
    subject: string | null;
    body: string | null;
    status: string;
  };
}) {
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState(draft.status);

  async function copyBody() {
    const body =
      (document.getElementById("body") as HTMLTextAreaElement | null)?.value ??
      "";
    await navigator.clipboard.writeText(body);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <form action={updateDraftAction} className="flex max-w-3xl flex-col gap-4">
      <input type="hidden" name="id" value={draft.id} />
      <input type="hidden" name="status" value={status} />

      <div className="flex flex-col gap-2">
        <label htmlFor="subject" className="text-sm font-medium">
          Subject
        </label>
        <Input id="subject" name="subject" defaultValue={draft.subject ?? ""} />
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="body" className="text-sm font-medium">
          Body
        </label>
        <Textarea
          id="body"
          name="body"
          rows={18}
          defaultValue={draft.body ?? ""}
          className="font-mono text-sm"
        />
      </div>

      <div className="flex items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={copyBody}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          {copied ? "Copied" : "Copy body"}
        </Button>

        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button type="submit" size="sm">
          Save
        </Button>
      </div>
    </form>
  );
}

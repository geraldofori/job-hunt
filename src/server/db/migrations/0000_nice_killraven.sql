CREATE TABLE `companies` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`domain` text,
	`linkedin_url` text,
	`careers_url` text,
	`ats_provider` text,
	`industry` text,
	`size` text,
	`notes` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `companies_name_unique` ON `companies` (`name`);--> statement-breakpoint
CREATE TABLE `contacts` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`company_id` integer,
	`full_name` text NOT NULL,
	`role` text,
	`department` text,
	`linkedin_url` text,
	`email` text,
	`email_source` text,
	`email_verified` integer DEFAULT false,
	`email_status` text DEFAULT 'unknown',
	`phone` text,
	`source` text,
	`notes` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`updated_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`company_id`) REFERENCES `companies`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE INDEX `contacts_company_idx` ON `contacts` (`company_id`);--> statement-breakpoint
CREATE TABLE `jobs` (
	`id` text PRIMARY KEY NOT NULL,
	`company_id` integer,
	`site` text NOT NULL,
	`title` text NOT NULL,
	`company` text NOT NULL,
	`location` text,
	`work_model` text,
	`job_url` text,
	`job_url_direct` text,
	`description` text,
	`language` text DEFAULT 'unknown',
	`date_posted` text,
	`easy_apply` integer DEFAULT false,
	`score` real,
	`status` text DEFAULT 'new' NOT NULL,
	`first_seen` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`applied_at` text,
	`cover_letter_path` text,
	`notes` text,
	FOREIGN KEY (`company_id`) REFERENCES `companies`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `jobs_status_idx` ON `jobs` (`status`);--> statement-breakpoint
CREATE INDEX `jobs_score_idx` ON `jobs` (`score`);--> statement-breakpoint
CREATE INDEX `jobs_site_idx` ON `jobs` (`site`);--> statement-breakpoint
CREATE TABLE `outreach_messages` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`contact_id` integer,
	`job_id` text,
	`channel` text DEFAULT 'email' NOT NULL,
	`subject` text,
	`body` text,
	`status` text DEFAULT 'draft' NOT NULL,
	`sent_at` text,
	`replied_at` text,
	`notes` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`contact_id`) REFERENCES `contacts`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`job_id`) REFERENCES `jobs`(`id`) ON UPDATE no action ON DELETE set null
);
--> statement-breakpoint
CREATE INDEX `outreach_contact_idx` ON `outreach_messages` (`contact_id`);--> statement-breakpoint
CREATE TABLE `runs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`type` text NOT NULL,
	`started_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`finished_at` text,
	`new_jobs` integer DEFAULT 0,
	`new_contacts` integer DEFAULT 0,
	`source_counts` text,
	`error` text,
	`notes` text
);
--> statement-breakpoint
CREATE TABLE `settings` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text
);

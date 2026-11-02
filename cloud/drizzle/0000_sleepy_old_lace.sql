CREATE TABLE `attempts` (
	`id` text PRIMARY KEY NOT NULL,
	`task_id` text NOT NULL,
	`answer` text NOT NULL,
	`assisted` integer NOT NULL,
	`version` integer NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `evidence` (
	`id` text PRIMARY KEY NOT NULL,
	`knowledge_id` text NOT NULL,
	`session_id` text NOT NULL,
	`data` text NOT NULL,
	FOREIGN KEY (`knowledge_id`) REFERENCES `knowledge`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`session_id`) REFERENCES `sessions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `evidence_by_knowledge` ON `evidence` (`knowledge_id`);--> statement-breakpoint
CREATE TABLE `exposures` (
	`id` text PRIMARY KEY NOT NULL,
	`knowledge_id` text NOT NULL,
	`level` text NOT NULL,
	`note` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`knowledge_id`) REFERENCES `knowledge`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `transaction_guards` (
	`id` text PRIMARY KEY NOT NULL
);
--> statement-breakpoint
CREATE TABLE `knowledge` (
	`id` text PRIMARY KEY NOT NULL,
	`data` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `library_state` (
	`id` integer PRIMARY KEY NOT NULL,
	`revision` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `relations` (
	`id` text PRIMARY KEY NOT NULL,
	`from_id` text NOT NULL,
	`to_id` text NOT NULL,
	`label` text NOT NULL,
	`explanation` text NOT NULL,
	`session_id` text,
	FOREIGN KEY (`from_id`) REFERENCES `knowledge`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`to_id`) REFERENCES `knowledge`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`session_id`) REFERENCES `sessions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `reviews` (
	`id` text PRIMARY KEY NOT NULL,
	`task_id` text NOT NULL,
	`version` integer NOT NULL,
	`data` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`id`) REFERENCES `attempts`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `one_review_per_version` ON `reviews` (`task_id`,`version`);--> statement-breakpoint
CREATE TABLE `sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`external_id` text NOT NULL,
	`hash` text NOT NULL,
	`payload` text NOT NULL,
	`imported_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `sessions_external_id_unique` ON `sessions` (`external_id`);--> statement-breakpoint
CREATE TABLE `knowledge_tags` (
	`knowledge_id` text NOT NULL,
	`normalized` text NOT NULL,
	`label` text NOT NULL,
	PRIMARY KEY(`knowledge_id`, `normalized`),
	FOREIGN KEY (`knowledge_id`) REFERENCES `knowledge`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `task_sessions` (
	`task_id` text NOT NULL,
	`session_id` text NOT NULL,
	PRIMARY KEY(`task_id`, `session_id`),
	FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`session_id`) REFERENCES `sessions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `tasks` (
	`id` text PRIMARY KEY NOT NULL,
	`knowledge_id` text NOT NULL,
	`data` text NOT NULL,
	`card` text NOT NULL,
	`due` text NOT NULL,
	`version` integer NOT NULL,
	FOREIGN KEY (`knowledge_id`) REFERENCES `knowledge`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `tasks_by_due` ON `tasks` (`due`);
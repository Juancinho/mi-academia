CREATE TABLE `conversation_sessions` (
	`conversation_id` text NOT NULL,
	`session_id` text NOT NULL,
	PRIMARY KEY(`conversation_id`, `session_id`),
	FOREIGN KEY (`conversation_id`) REFERENCES `conversations`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`session_id`) REFERENCES `sessions`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `conversation_versions` (
	`id` text PRIMARY KEY NOT NULL,
	`conversation_id` text NOT NULL,
	`data` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`conversation_id`) REFERENCES `conversations`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `conversations` (
	`id` text PRIMARY KEY NOT NULL,
	`data` text NOT NULL,
	`hash` text NOT NULL,
	`revision` integer NOT NULL,
	`updated_at` text NOT NULL
);
CREATE VIRTUAL TABLE conversation_fts USING fts5(id UNINDEXED,title,body,tokenize='unicode61 remove_diacritics 2',prefix='2 3 4');
--> statement-breakpoint
CREATE TRIGGER conversation_fts_insert AFTER INSERT ON conversations BEGIN INSERT INTO conversation_fts(id,title,body) VALUES(new.id,json_extract(new.data,'$.title'),new.data); END;
--> statement-breakpoint
CREATE TRIGGER conversation_fts_update AFTER UPDATE ON conversations BEGIN DELETE FROM conversation_fts WHERE id=old.id; INSERT INTO conversation_fts(id,title,body) VALUES(new.id,json_extract(new.data,'$.title'),new.data); END;
--> statement-breakpoint
CREATE TRIGGER conversation_fts_delete AFTER DELETE ON conversations BEGIN DELETE FROM conversation_fts WHERE id=old.id; END;

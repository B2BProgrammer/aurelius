/**
 * ENTRY POINT of the Herald (client-comms).
 *
 * Run from the client-comms folder:
 *     npm start        compile src/*.ts -> dist/*.js, then run dist/server.js
 *     npm run dev      run the TypeScript directly (tsx), restart on every save
 *
 * What starts:
 *     server.ts -> app.ts (endpoints + Swagger) -> skills/ -> compose/composer.ts
 *                                                  -> clients/liaison.ts (HTTP to :8102)
 *                                                  -> compose/llm.ts (Claude, optional)
 */
import { AuditLog } from "./audit.js";
import { createApp } from "./app.js";
import { LiaisonClient } from "./clients/liaison.js";
import { Composer } from "./compose/composer.js";
import { ClaudeWriter } from "./compose/llm.js";
import { checkStartupSecurity, getConfig, loadEnvFiles, useLlm } from "./config.js";
import { getLogger } from "./logger.js";

const log = getLogger("herald");

loadEnvFiles();
const config = getConfig();
checkStartupSecurity(config); // fail closed

const writer = useLlm(config) ? new ClaudeWriter(config) : null;
const composer = new Composer(config, new LiaisonClient(config), writer);
const app = createApp({ config, composer, audit: new AuditLog(config.auditFile) });

app.listen(config.port, config.host, () => {
  log.info(`herald_started port=${config.port} mode=${composer.mode} liaison=${config.liaisonUrl}`);
  console.log(`Herald (client-comms) on http://${config.host}:${config.port}`);
  console.log(`Swagger UI:            http://${config.host}:${config.port}/docs`);
  console.log(`Drafting mode:         ${composer.mode}   (Liaison at ${config.liaisonUrl})`);
});

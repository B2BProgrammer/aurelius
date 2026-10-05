/**
 * ENTRY POINT of the Liaison (crm-sync).
 *
 * Run from the crm-sync folder:
 *     npm start        compile src/*.ts -> dist/*.js, then run dist/server.js
 *     npm run dev      run the TypeScript directly (tsx), restart on every save
 *
 * What starts:
 *     server.ts -> app.ts (endpoints + Swagger) -> skills/ -> store/crmStore.ts (data\crm.json)
 */
import { AuditLog } from "./audit.js";
import { createApp } from "./app.js";
import { checkStartupSecurity, getConfig, loadEnvFiles } from "./config.js";
import { getLogger } from "./logger.js";
import { CrmStore } from "./store/crmStore.js";

const log = getLogger("liaison");

loadEnvFiles();
const config = getConfig();
checkStartupSecurity(config); // fail closed

const store = new CrmStore(config);
const audit = new AuditLog(config.auditFile);
const app = createApp({ config, store, audit });

app.listen(config.port, config.host, () => {
  log.info(`liaison_started port=${config.port} households=${store.clientIds().length} data=${config.dataFile}`);
  console.log(`Liaison (crm-sync) on http://${config.host}:${config.port}`);
  console.log(`Swagger UI:          http://${config.host}:${config.port}/docs`);
});

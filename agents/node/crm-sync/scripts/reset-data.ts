/**
 * Reset the CRM to the sample data: copies data\crm.seed.json over data\crm.json.
 * Usage:  npm run reset-data     (stop the server first)
 */
import { copyFileSync } from "node:fs";

import { getConfig, loadEnvFiles } from "../src/config.js";

loadEnvFiles();
const { seedFile, dataFile } = getConfig();
copyFileSync(seedFile, dataFile);
console.log(`CRM reset: ${dataFile} <- ${seedFile}`);

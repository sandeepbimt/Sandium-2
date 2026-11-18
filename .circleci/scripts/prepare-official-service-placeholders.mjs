// Upstream-supported external official build configuration, NOT credentials.
// https://github.com/brave/brave-browser/wiki/Build-configuration
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
export const NAMES = ['brave_services_key', 'service_key_search', 'service_key_stt', 'service_key_aichat'];
export const PLACEHOLDER = 'sandium-external-build-no-service-credentials';
export function prepare(core, EnvConfig, emit = console.log) {
  const envPath = path.join(core, '.env');
  if (!fs.existsSync(envPath)) throw new Error('Official service configuration requires existing .env');
  const config = new EnvConfig(core);
  const additions = [];
  const statuses = [];
  for (const name of NAMES) {
    const value = config.getAny([name]);
    if (value !== undefined && value !== null && typeof value !== 'string') {
      throw new Error('Invalid service configuration type: '+name);
    }
    if (value === undefined || value === null || value.trim() === '') {
      additions.push(`${name}=${PLACEHOLDER}`);
      statuses.push([name, 'documented-placeholder']);
    } else {
      statuses.push([name, value === PLACEHOLDER ? 'documented-placeholder' : 'existing-value-preserved']);
    }
  }
  // Resolve every value before writing; never replace a nonempty resolved key,
  // including keys supplied through include_env or package configuration.
  if (additions.length) fs.appendFileSync(envPath, '\n# Non-authenticating placeholders permitted by upstream external-build docs.\n'+additions.join('\n')+'\n');
  const verify = new EnvConfig(core);
  for (const [name] of statuses) {
    const value=verify.getAny([name]);
    if (typeof value !== 'string' || value.trim() === '') throw new Error('Official service configuration unresolved: '+name);
  }
  for (const [name,status] of statuses) emit('OFFICIAL_SERVICE_CONFIG='+name+':'+status);
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const core=path.resolve(process.argv[2]);
  const {default: EnvConfig}=await import(pathToFileURL(path.join(core,'build/commands/lib/envConfig.ts')).href);
  prepare(core,EnvConfig);
}

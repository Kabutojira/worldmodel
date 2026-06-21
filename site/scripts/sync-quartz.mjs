import { cpSync, existsSync, mkdirSync, rmSync, symlinkSync, unlinkSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const siteDir = path.resolve(here, "..")
const sourceDir = path.join(siteDir, "node_modules", "@jackyzha0", "quartz", "quartz")
const targetDir = path.join(siteDir, "quartz")
const binDir = path.join(siteDir, "node_modules", ".bin")
const localBootstrap = path.join(targetDir, "bootstrap-cli.mjs")
const quartzBin = path.join(binDir, "quartz")

if (!existsSync(sourceDir)) {
  console.error(`Quartz source directory not found: ${sourceDir}`)
  process.exit(1)
}

rmSync(targetDir, { recursive: true, force: true })
mkdirSync(path.dirname(targetDir), { recursive: true })
cpSync(sourceDir, targetDir, { recursive: true })

mkdirSync(binDir, { recursive: true })
try {
  unlinkSync(quartzBin)
} catch {}
try {
  symlinkSync(path.relative(binDir, localBootstrap), quartzBin)
} catch {
  writeFileSync(quartzBin, `#!/usr/bin/env bash\nexec node \"${localBootstrap}\" \"$@\"\n`, { mode: 0o755 })
}

console.log(`Synced Quartz runtime source into ${targetDir}`)
console.log(`Bound local quartz CLI to ${quartzBin}`)

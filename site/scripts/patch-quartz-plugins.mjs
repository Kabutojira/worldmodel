import { existsSync, readFileSync, writeFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const here = path.dirname(fileURLToPath(import.meta.url))
const siteDir = path.resolve(here, "..")

const replacements = [
  {
    relativePath: ".quartz/plugins/folder-page/dist/index.js",
    oldString: `    if (trie) {
      const folder = trie.findNode(slug2.split("/"));
      if (!folder) return null;
      allPagesInFolder = pagesFromTrie(folder, options.showSubfolders);
    } else {
      allPagesInFolder = pagesFromAllFiles(allFiles ?? [], slug2, options.showSubfolders);
    }
`,
    newString: `    if (trie) {
      const folderPath = slug2.endsWith("/index") ? slug2.slice(0, -"/index".length) : slug2;
      const folder = trie.findNode(folderPath.split("/"));
      if (folder) {
        allPagesInFolder = pagesFromTrie(folder, options.showSubfolders);
      } else {
        allPagesInFolder = pagesFromAllFiles(allFiles ?? [], slug2, options.showSubfolders);
      }
    } else {
      allPagesInFolder = pagesFromAllFiles(allFiles ?? [], slug2, options.showSubfolders);
    }
`,
  },
  {
    relativePath: ".quartz/plugins/folder-page/src/components/FolderContent.tsx",
    oldString: `    if (trie) {
      const folder = trie.findNode(slug.split("/"));
      if (!folder) return null;
      allPagesInFolder = pagesFromTrie(folder, options.showSubfolders);
    } else {
      allPagesInFolder = pagesFromAllFiles(allFiles ?? [], slug, options.showSubfolders);
    }
`,
    newString: `    if (trie) {
      const folderPath = slug.endsWith("/index") ? slug.slice(0, -"/index".length) : slug;
      const folder = trie.findNode(folderPath.split("/"));
      if (folder) {
        allPagesInFolder = pagesFromTrie(folder, options.showSubfolders);
      } else {
        allPagesInFolder = pagesFromAllFiles(allFiles ?? [], slug, options.showSubfolders);
      }
    } else {
      allPagesInFolder = pagesFromAllFiles(allFiles ?? [], slug, options.showSubfolders);
    }
`,
  },
]

let applied = 0
for (const replacement of replacements) {
  const target = path.join(siteDir, replacement.relativePath)
  if (!existsSync(target)) {
    console.error(`Quartz plugin file not found: ${target}`)
    process.exit(1)
  }

  const current = readFileSync(target, "utf8")
  if (current.includes(replacement.newString)) {
    console.log(`Quartz plugin patch already present: ${replacement.relativePath}`)
    continue
  }
  if (!current.includes(replacement.oldString)) {
    console.error(`Quartz plugin patch anchor not found: ${replacement.relativePath}`)
    process.exit(1)
  }

  writeFileSync(target, current.replace(replacement.oldString, replacement.newString), "utf8")
  applied += 1
  console.log(`Patched Quartz plugin file: ${replacement.relativePath}`)
}

console.log(`Quartz plugin patch complete. Files modified: ${applied}`)

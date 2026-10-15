import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

let failures = 0;

function check(path: string) {
  if (/\.(ts|tsx|css)$/.test(path) && !path.endsWith(".d.ts")) {
    readFileSync(path, "utf8")
      .split(/\r?\n/)
      .forEach((line, index) => {
        const length = Array.from(line).length;
        if (length > 100) {
          console.error(`${path}:${index + 1}: ${length} characters (maximum 100)`);
          failures += 1;
        }
      });
  }
}

function walk(directory: string) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) walk(path);
    else check(path);
  }
}

for (const directory of ["app", "components", "lib", "scripts", "tests"]) walk(directory);
for (const path of ["proxy.ts", "next.config.ts"]) check(path);
process.exitCode = failures ? 1 : 0;

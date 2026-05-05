const { compileFromFile } = require("json-schema-to-typescript");
const fs = require("fs");
const path = require("path");

const SRC = path.resolve(__dirname, "../types/wire.schema.json");
const OUT = path.resolve(__dirname, "../types/wire.gen.d.ts");

compileFromFile(SRC, {
  bannerComment:
    "// AUTO-GENERATED. Do not edit by hand. Run `npm run gen` from client/.",
  unreachableDefinitions: true,
})
  .then((ts) => {
    fs.writeFileSync(OUT, ts);
    console.log(`wrote ${OUT}`);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });

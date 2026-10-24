import { DESCRIPTOR_FILES } from "./descriptors.js";
import { describe, register } from "./engine.js";

for (const d of DESCRIPTOR_FILES) register(d);

export { describe, descriptorFor, template, when, worstRisk } from "./engine.js";
export { dropsToXrp, hexText } from "./formats.js";
export type { Ctx, Descriptor, Line, Preview, Risk, Tx } from "./types.js";
export default describe;

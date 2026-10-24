// Every metadata file in format/. Add a type = add its JSON to format/ and import it in its family file.
import { CORE_DESCRIPTORS } from "./descriptors-core.js";
import { LENDING_DESCRIPTORS } from "./descriptors-lending.js";
import type { Descriptor } from "./types.js";

export const DESCRIPTOR_FILES: Descriptor[] = [...CORE_DESCRIPTORS, ...LENDING_DESCRIPTORS];

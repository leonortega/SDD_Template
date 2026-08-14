import { describe, expect, it } from "vitest";
import { packageName } from "../../src/index.js";

describe("<pkgName>", () => {
  it("identifies itself", () => {
    expect(packageName()).toBe("<pkgName>");
  });
});

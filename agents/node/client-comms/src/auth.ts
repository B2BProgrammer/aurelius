/**
 * Service-token check: only other agents may call the Herald.
 *
 * LEARN: crypto.timingSafeEqual is Node's constant-time comparison (like
 * Python's hmac.compare_digest). A plain === stops at the first wrong
 * character, and that timing difference can leak the token.
 */
import { timingSafeEqual } from "node:crypto";

import type { RequestHandler } from "express";

import type { Config } from "./config.js";

export function requireService(config: Config): RequestHandler {
  const expected = Buffer.from(config.serviceToken);
  return (req, res, next) => {
    const header = req.get("authorization") ?? "";
    const supplied = Buffer.from(header.toLowerCase().startsWith("bearer ") ? header.slice(7) : "");
    const valid = supplied.length === expected.length && timingSafeEqual(supplied, expected);
    if (!valid) {
      res.set("WWW-Authenticate", "Bearer");
      res.status(401).json({ detail: "Invalid or missing service token" });
      return;
    }
    next();
  };
}

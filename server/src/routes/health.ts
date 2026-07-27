import { Router } from "express";
import { prisma } from "../lib/prisma.js";

const router: ReturnType<typeof Router> = Router();

router.get("/", async (_req, res) => {
  try {
    // Ping PG
    await prisma.$queryRaw`SELECT 1`;
    res.json({
      status: "online",
      service: "CodeLens Express Backend",
      timestamp: new Date().toISOString(),
      database: "connected",
    });
  } catch (error) {
    res.status(500).json({
      status: "degraded",
      service: "CodeLens Express Backend",
      error: String(error),
    });
  }
});

export default router;

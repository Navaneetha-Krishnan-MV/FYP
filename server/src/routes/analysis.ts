import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { getOrCreateDefaultUser } from "../lib/defaultUser.js";
import { triggerBugAnalysis } from "../services/aiClient.js";

const router: ReturnType<typeof Router> = Router();

// Trigger AGTR bug analysis
router.post("/trigger", async (req, res, next) => {
  try {
    const { bugReportId } = req.body;
    if (!bugReportId) {
      return res.status(400).json({ error: "bugReportId is required" });
    }

    const bugReport = await prisma.bugReport.findUnique({
      where: { id: bugReportId },
    });

    if (!bugReport) {
      return res.status(404).json({ error: "Bug report not found" });
    }

    const user = await getOrCreateDefaultUser();

    // Create pending analysis record
    const analysis = await prisma.analysisResult.create({
      data: {
        bugReportId,
        projectId: bugReport.projectId,
        userId: user.id,
        status: "pending",
      },
    });

    // Trigger AI Server async pipeline
    triggerBugAnalysis(bugReportId).catch((err) => {
      console.error(`Background AGTR analysis failed for bug ${bugReportId}:`, err);
    });

    res.status(202).json({
      message: "AGTR Analysis triggered successfully",
      analysisId: analysis.id,
    });
  } catch (error) {
    next(error);
  }
});

// Get analysis result by ID
router.get("/:id", async (req, res, next) => {
  try {
    const { id } = req.params;
    const analysis = await prisma.analysisResult.findUnique({
      where: { id },
      include: {
        bugReport: true,
        project: {
          select: {
            id: true,
            name: true,
            repoUrl: true,
          },
        },
      },
    });

    if (!analysis) {
      return res.status(404).json({ error: "Analysis result not found" });
    }

    res.json(analysis);
  } catch (error) {
    next(error);
  }
});

// Get all analyses for a project
router.get("/project/:projectId", async (req, res, next) => {
  try {
    const { projectId } = req.params;
    const analyses = await prisma.analysisResult.findMany({
      where: { projectId },
      orderBy: { createdAt: "desc" },
      include: {
        bugReport: {
          select: {
            id: true,
            title: true,
            severity: true,
            externalBugId: true,
          },
        },
      },
    });

    res.json(analyses);
  } catch (error) {
    next(error);
  }
});

export default router;

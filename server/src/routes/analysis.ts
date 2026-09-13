import { Router } from "express";
import { prisma } from "../lib/prisma.js";
import { getOrCreateDefaultUser } from "../lib/defaultUser.js";

const router: ReturnType<typeof Router> = Router();

// AnalysisResult is the durable MVP queue; the Python worker claims exact IDs.
router.post("/trigger", async (req, res, next) => {
  try {
    const { bugReportId } = req.body;
    if (typeof bugReportId !== "string" || !bugReportId) {
      return res.status(400).json({ error: "bugReportId is required" });
    }

    const bugReport = await prisma.bugReport.findUnique({
      where: { id: bugReportId },
    });

    if (!bugReport) {
      return res.status(404).json({ error: "Bug report not found" });
    }

    const project = await prisma.project.findUnique({ where: { id: bugReport.projectId } });
    if (project?.status !== "READY") {
      return res.status(409).json({ error: "Project must finish indexing before analysis" });
    }

    const user = await getOrCreateDefaultUser();

    // Create pending analysis record
    const analysis = await prisma.analysisResult.create({
      data: {
        bugReportId,
        projectId: bugReport.projectId,
        userId: user.id,
        status: "pending",
        evidenceContext: { engine: "agentic", schema_version: 1, stage: "queued" },
      },
    });

    res.status(202).json({
      message: "Analysis queued successfully",
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

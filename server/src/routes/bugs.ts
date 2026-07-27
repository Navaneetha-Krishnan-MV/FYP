import { Router, type RequestHandler } from "express";
import multer from "multer";
import path from "path";
import fs from "fs";
import { prisma } from "../lib/prisma.js";
import { getOrCreateDefaultUser } from "../lib/defaultUser.js";
import { BugSeverity } from "../../generated/prisma/enums.js";

const router: ReturnType<typeof Router> = Router();

const upload = multer({ dest: path.join(process.cwd(), "uploads") });

// Parse CSV content helper
function parseBugCsv(csvText: string) {
  const lines = csvText.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length === 0) return [];

  const headers = lines[0]!.split(",").map((h) => h.trim().toLowerCase());
  const bugIdIdx = headers.findIndex((h) => h === "bug_id" || h === "id");
  const titleIdx = headers.findIndex((h) => h === "title" || h === "summary" || h === "name");
  const descIdx = headers.findIndex((h) => h === "description" || h === "desc" || h === "details");
  const severityIdx = headers.findIndex((h) => h === "severity" || h === "priority");
  const reporterIdx = headers.findIndex((h) => h === "reporter" || h === "author");

  const results: Array<{
    externalBugId?: string;
    title: string;
    description: string;
    severity: BugSeverity;
    reporter?: string;
  }> = [];

  for (let i = 1; i < lines.length; i++) {
    // Regex to parse CSV line respecting quotes
    const row = lines[i]!.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g) || lines[i]!.split(",");
    const cleanRow = row.map((cell) => cell.replace(/^"|"$/g, "").trim());

    const title = titleIdx !== -1 && cleanRow[titleIdx] ? cleanRow[titleIdx]! : `Bug #${i}`;
    const description = descIdx !== -1 && cleanRow[descIdx] ? cleanRow[descIdx]! : title;
    const bugId = bugIdIdx !== -1 ? cleanRow[bugIdIdx] : `BUG-${i}`;
    const reporter = reporterIdx !== -1 ? cleanRow[reporterIdx] : undefined;

    let severity: BugSeverity = BugSeverity.MEDIUM;
    if (severityIdx !== -1 && cleanRow[severityIdx]) {
      const s = cleanRow[severityIdx]!.toUpperCase();
      if (s.includes("CRIT")) severity = BugSeverity.CRITICAL;
      else if (s.includes("HIGH")) severity = BugSeverity.HIGH;
      else if (s.includes("LOW")) severity = BugSeverity.LOW;
    }

    const parsedBug: {
      externalBugId?: string;
      title: string;
      description: string;
      severity: BugSeverity;
      reporter?: string;
    } = {
      title,
      description,
      severity,
    };

    if (bugId) {
      parsedBug.externalBugId = bugId;
    }

    if (reporter) {
      parsedBug.reporter = reporter;
    }

    results.push(parsedBug);
  }

  return results;
}

// Create single bug report
router.post("/", async (req, res, next) => {
  try {
    const { projectId, title, description, severity, stepsToReproduce, externalBugId, reporter } = req.body;

    if (!projectId || !title || !description) {
      return res.status(400).json({ error: "projectId, title, and description are required" });
    }

    const user = await getOrCreateDefaultUser();

    const bugReport = await prisma.bugReport.create({
      data: {
        projectId,
        title,
        description,
        severity: (severity as BugSeverity) || BugSeverity.MEDIUM,
        stepsToReproduce: stepsToReproduce || null,
        externalBugId: externalBugId || null,
        reporter: reporter || user.name,
        source: "manual",
        userId: user.id,
      },
    });

    res.status(201).json(bugReport);
  } catch (error) {
    next(error);
  }
});

// CSV Upload for multiple bug reports
router.post("/csv", upload.single("file") as RequestHandler, async (req, res, next) => {
  try {
    const { projectId } = req.body;
    if (!projectId) {
      return res.status(400).json({ error: "projectId is required" });
    }

    if (!req.file) {
      return res.status(400).json({ error: "CSV file is required" });
    }

    const fileContent = fs.readFileSync(req.file.path, "utf-8");
    fs.unlinkSync(req.file.path); // clean up uploaded file

    const parsedBugs = parseBugCsv(fileContent);
    if (parsedBugs.length === 0) {
      return res.status(400).json({ error: "No valid bug reports parsed from CSV" });
    }

    const user = await getOrCreateDefaultUser();

    const createdBugs = await prisma.$transaction(
      parsedBugs.map((bug) =>
        prisma.bugReport.create({
          data: {
            projectId,
            title: bug.title,
            description: bug.description,
            severity: bug.severity,
            externalBugId: bug.externalBugId || null,
            reporter: bug.reporter || user.name,
            source: "csv",
            userId: user.id,
          },
        })
      )
    );

    res.status(201).json({
      count: createdBugs.length,
      bugs: createdBugs,
    });
  } catch (error) {
    next(error);
  }
});

// List bugs for project
router.get("/project/:projectId", async (req, res, next) => {
  try {
    const { projectId } = req.params;
    const bugs = await prisma.bugReport.findMany({
      where: { projectId },
      orderBy: { createdAt: "desc" },
      include: {
        analysisResults: {
          orderBy: { createdAt: "desc" },
          take: 1,
        },
      },
    });
    res.json(bugs);
  } catch (error) {
    next(error);
  }
});

export default router;

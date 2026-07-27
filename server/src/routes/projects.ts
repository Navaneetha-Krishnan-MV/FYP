import { Router, type RequestHandler } from "express";
import multer from "multer";
import path from "path";
import fs from "fs";
import { prisma } from "../lib/prisma.js";
import { getOrCreateDefaultUser } from "../lib/defaultUser.js";
import { triggerRepositoryIndexing } from "../services/aiClient.js";

const router: ReturnType<typeof Router> = Router();

const uploadDir = path.join(process.cwd(), "uploads");
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => cb(null, `${Date.now()}-${file.originalname}`),
});

const upload = multer({ storage });

// List all projects
router.get("/", async (_req, res, next) => {
  try {
    const projects = await prisma.project.findMany({
      orderBy: { createdAt: "desc" },
      include: {
        _count: {
          select: {
            codeChunks: true,
            commits: true,
            bugReports: true,
          },
        },
      },
    });
    res.json(projects);
  } catch (error) {
    next(error);
  }
});

// Get single project
router.get("/:id", async (req, res, next) => {
  try {
    const { id } = req.params;
    const project = await prisma.project.findUnique({
      where: { id },
      include: {
        codeChunks: { take: 50 },
        commits: { take: 20, orderBy: { committedAt: "desc" } },
        bugReports: { orderBy: { createdAt: "desc" } },
      },
    });

    if (!project) {
      return res.status(404).json({ error: "Project not found" });
    }

    res.json(project);
  } catch (error) {
    next(error);
  }
});

// Create project from GitHub URL
router.post("/", async (req, res, next) => {
  try {
    const { name, description, repoUrl } = req.body;
    if (!name || !repoUrl) {
      return res.status(400).json({ error: "Name and repoUrl are required" });
    }

    const user = await getOrCreateDefaultUser();

    const project = await prisma.project.create({
      data: {
        name,
        description: description || "",
        repoUrl,
        repoType: "github",
        localPath: "",
        status: "PENDING",
        userId: user.id,
      },
    });

    // Trigger async indexing background job on AI Server
    triggerRepositoryIndexing(project.id, repoUrl).catch((err) => {
      console.error(`Background indexing failed for project ${project.id}:`, err);
    });

    res.status(201).json(project);
  } catch (error) {
    next(error);
  }
});

// Create project from ZIP Upload
router.post("/zip", upload.single("zipFile") as RequestHandler, async (req, res, next) => {
  try {
    const { name, description } = req.body;
    if (!req.file) {
      return res.status(400).json({ error: "ZIP file is required" });
    }

    const user = await getOrCreateDefaultUser();

    const project = await prisma.project.create({
      data: {
        name: name || req.file.originalname.replace(".zip", ""),
        description: description || "",
        repoType: "zip",
        localPath: req.file.path,
        status: "PENDING",
        userId: user.id,
      },
    });

    // Trigger async indexing
    triggerRepositoryIndexing(project.id, undefined, req.file.path).catch((err) => {
      console.error(`Background indexing failed for zip project ${project.id}:`, err);
    });

    res.status(201).json(project);
  } catch (error) {
    next(error);
  }
});

// Re-index project
router.post("/:id/index", async (req, res, next) => {
  try {
    const { id } = req.params;
    const project = await prisma.project.findUnique({ where: { id } });

    if (!project) {
      return res.status(404).json({ error: "Project not found" });
    }

    await prisma.project.update({
      where: { id },
      data: { status: "PENDING", errorMsg: null },
    });

    triggerRepositoryIndexing(project.id, project.repoUrl || undefined, project.localPath || undefined).catch((err) => {
      console.error(`Background re-indexing failed for project ${project.id}:`, err);
    });

    res.json({ message: "Indexing started", projectId: project.id });
  } catch (error) {
    next(error);
  }
});

export default router;

import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import healthRouter from "./src/routes/health.js";
import projectsRouter from "./src/routes/projects.js";
import bugsRouter from "./src/routes/bugs.js";
import analysisRouter from "./src/routes/analysis.js";
import { errorHandler } from "./src/middleware/errorHandler.js";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true, limit: "50mb" }));

// Register routes
app.use("/api/health", healthRouter);
app.use("/api/projects", projectsRouter);
app.use("/api/bugs", bugsRouter);
app.use("/api/analysis", analysisRouter);

// Error middleware
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`🚀 CodeLens AI Express Server listening on http://localhost:${PORT}`);
});
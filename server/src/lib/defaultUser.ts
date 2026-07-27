import { prisma } from "./prisma.js";

export async function getOrCreateDefaultUser() {
  let user = await prisma.user.findFirst();
  if (!user) {
    user = await prisma.user.create({
      data: {
        email: "demo@codelens.ai",
        name: "Demo Developer",
        avatarUrl: "https://api.dicebear.com/7.x/bottts/svg?seed=CodeLens",
      },
    });
  }
  return user;
}

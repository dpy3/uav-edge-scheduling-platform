import { createFileRoute } from "@tanstack/react-router"

import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "概览 - UAV Edge Scheduling",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()

  return (
    <div>
      <div>
        <h1 className="text-2xl truncate max-w-sm">
          欢迎，{currentUser?.full_name || currentUser?.email}
        </h1>
        <p className="text-muted-foreground">
          在“调度运行”中导入场景、运行算法并保存实验结果。
        </p>
      </div>
    </div>
  )
}

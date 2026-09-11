import { client } from "@/client/client.gen"

export type SchedulingMethod = "greedy" | "lpt" | "ga" | "cpsat"

export type SchedulingTask = {
  task_id: number
  node_id: number
  node_name: string
  release_time: number
  start_time: number
  duration: number
  end_time: number
  priority: number
  data_size_mb: number
  deadline: number
  workload_mcycles: number
}

export type EdgeTaskInput = {
  task_id?: number
  workload_mcycles: number
  data_size_mb?: number
  release_time?: number
  deadline?: number
  priority?: number
}

export type EdgeNodeInput = {
  name: string
  compute_capacity: number
  bandwidth_mbps?: number
}

export type SchedulingScenario = {
  tasks: EdgeTaskInput[]
  nodes: EdgeNodeInput[]
  source_name: string
}

export type SchedulingRun = {
  id: string
  owner_id: string
  method: SchedulingMethod
  status: string
  n_tasks: number
  n_nodes: number
  seed: number
  time_limit: number
  makespan: number
  wall_time_s: number
  tasks: SchedulingTask[]
  nodes: EdgeNodeInput[]
  source_name: string
  created_at?: string | null
}

export type SchedulingRunRequest = {
  n_tasks: number
  n_nodes: number
  seed: number
  method: SchedulingMethod
  time_limit: number
  scenario?: SchedulingScenario
}

export type SchedulingComparisonRequest = Omit<SchedulingRunRequest, "method"> & {
  methods: SchedulingMethod[]
}

type SchedulingRunsResponse = {
  data: SchedulingRun[]
  count: number
}

const auth = [{ scheme: "bearer" as const, type: "http" as const }]

export async function createSchedulingRun(
  body: SchedulingRunRequest,
): Promise<SchedulingRun> {
  const response = await client.post({
    body,
    responseType: "json",
    security: auth,
    url: "/api/v1/scheduling/runs",
  })
  return response.data as SchedulingRun
}

export async function readSchedulingRuns(): Promise<SchedulingRunsResponse> {
  const response = await client.get({
    query: { limit: 20, skip: 0 },
    responseType: "json",
    security: auth,
    url: "/api/v1/scheduling/runs",
  })
  return response.data as SchedulingRunsResponse
}

export async function compareSchedulingMethods(
  body: SchedulingComparisonRequest,
): Promise<SchedulingRun[]> {
  const response = await client.post({
    body,
    responseType: "json",
    security: auth,
    url: "/api/v1/scheduling/compare",
  })
  return response.data as SchedulingRun[]
}

export async function importSchedulingScenario(file: File): Promise<SchedulingScenario> {
  const formData = new FormData()
  formData.append("file", file)
  const response = await client.post({
    body: formData,
    bodySerializer: (body) => body,
    responseType: "json",
    security: auth,
    url: "/api/v1/scheduling/import",
  })
  return response.data as SchedulingScenario
}

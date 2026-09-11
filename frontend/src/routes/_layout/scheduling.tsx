import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Activity, Clock3, Cpu, FileUp, Play, RefreshCw } from "lucide-react"
import type { FormEvent, ReactNode } from "react"
import { useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import { compareSchedulingMethods, createSchedulingRun, importSchedulingScenario, readSchedulingRuns, type SchedulingMethod, type SchedulingRun, type SchedulingScenario } from "@/lib/scheduling"

export const Route = createFileRoute("/_layout/scheduling")({
  component: Scheduling,
  head: () => ({ meta: [{ title: "UAV Edge Scheduling" }] }),
})

const methodLabels: Record<SchedulingMethod, string> = { greedy: "Greedy earliest finish", lpt: "Longest processing time", ga: "Genetic algorithm", cpsat: "CP-SAT exact solver", business: "Priority/deadline aware" }

function Scheduling() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [method, setMethod] = useState<SchedulingMethod>("greedy")
  const [nTasks, setNTasks] = useState(20)
  const [nNodes, setNNodes] = useState(4)
  const [seed, setSeed] = useState(42)
  const [timeLimit, setTimeLimit] = useState(5)
  const [latestRun, setLatestRun] = useState<SchedulingRun | null>(null)
  const [comparison, setComparison] = useState<SchedulingRun[]>([])
  const [scenario, setScenario] = useState<SchedulingScenario | undefined>()
  const [importMessage, setImportMessage] = useState("")
  const historyQuery = useQuery({ queryFn: readSchedulingRuns, queryKey: ["scheduling-runs"] })
  const refreshHistory = () => queryClient.invalidateQueries({ queryKey: ["scheduling-runs"] })
  const runMutation = useMutation({
    mutationFn: createSchedulingRun,
    onError: (error: Error) => showErrorToast(error.message),
    onSuccess: (run) => { setLatestRun(run); setComparison([]); refreshHistory(); showSuccessToast("调度完成，运行记录已保存") },
  })
  const compareMutation = useMutation({
    mutationFn: compareSchedulingMethods,
    onError: (error: Error) => showErrorToast(error.message),
    onSuccess: (runs) => { setComparison(runs); setLatestRun(runs[0] ?? null); refreshHistory(); showSuccessToast("算法对比完成，结果已保存") },
  })
  const nodeLoads = useMemo(() => {
    if (!latestRun) return []
    const loads = Array.from({ length: latestRun.n_nodes }, (_, nodeId) => {
      const tasks = latestRun.tasks.filter((task) => task.node_id === nodeId)
      return { nodeId, taskCount: tasks.length, totalDuration: tasks.reduce((sum, task) => sum + task.duration, 0) }
    })
    const maxLoad = Math.max(...loads.map((node) => node.totalDuration), 1)
    return loads.map((node) => ({ ...node, ratio: Math.round((node.totalDuration / maxLoad) * 100) }))
  }, [latestRun])
  const requestBase = { n_nodes: nNodes, n_tasks: nTasks, seed, time_limit: timeLimit, scenario }
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); runMutation.mutate({ ...requestBase, method }) }
  const compare = () => compareMutation.mutate({ ...requestBase, methods: ["greedy", "lpt", "ga", "cpsat", "business"] })
  const importFile = async (file?: File) => {
    if (!file) return
    try {
      const imported = await importSchedulingScenario(file)
      setScenario(imported); setNTasks(imported.tasks.length); setNNodes(imported.nodes.length)
      setImportMessage(`已加载 ${imported.source_name}: ${imported.tasks.length} 个任务、${imported.nodes.length} 个节点`)
      showSuccessToast("任务场景导入成功")
    } catch (error) { showErrorToast(error instanceof Error ? error.message : "导入失败") }
  }
  return <div className="flex flex-col gap-6">
    <div><h1 className="text-2xl font-bold tracking-tight">无人机边缘调度台</h1><p className="text-muted-foreground">导入任务场景，运行调度算法，并用同一输入比较 makespan 与求解耗时。</p></div>
    <Card><CardHeader><CardTitle>新建调度实验</CardTitle><CardDescription>未导入数据时按随机种子生成实例；导入后会使用上传的任务和节点参数。</CardDescription></CardHeader><CardContent><form className="grid gap-4 md:grid-cols-2 xl:grid-cols-5" onSubmit={submit}>
      <label className="grid gap-2 text-sm font-medium">求解方法<Select value={method} onValueChange={(value) => setMethod(value as SchedulingMethod)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{Object.entries(methodLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></label>
      <NumberField label="任务数量" min={1} max={300} value={nTasks} onChange={setNTasks} /><NumberField label="计算节点" min={1} max={32} value={nNodes} onChange={setNNodes} /><NumberField label="随机种子" min={0} value={seed} onChange={setSeed} />
      <div className="flex items-end"><Button className="w-full" disabled={runMutation.isPending || compareMutation.isPending} type="submit">{runMutation.isPending ? <RefreshCw className="animate-spin" /> : <Play />}{runMutation.isPending ? "求解中" : "开始调度"}</Button></div>
      <label className="grid gap-2 text-sm font-medium">GA / CP-SAT 上限（秒）<Input max={60} min={0.1} onChange={(event) => setTimeLimit(Number(event.target.value))} step={0.1} type="number" value={timeLimit} /></label>
      <div className="flex flex-wrap items-end gap-2 md:col-span-2 xl:col-span-3"><Button disabled={runMutation.isPending || compareMutation.isPending} onClick={compare} type="button" variant="secondary">{compareMutation.isPending ? <RefreshCw className="animate-spin" /> : <Activity />}一键算法对比</Button><label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border px-3 text-sm hover:bg-accent"><FileUp className="size-4" />导入 JSON/CSV<input accept=".json,.csv,application/json,text/csv" className="hidden" onChange={(event) => importFile(event.target.files?.[0])} type="file" /></label></div>
    </form>{importMessage ? <p className="mt-4 text-sm text-muted-foreground">{importMessage}</p> : null}</CardContent></Card>
    {comparison.length > 0 ? <ComparisonPanel runs={comparison} /> : null}
    {latestRun ? <><div className="grid gap-4 md:grid-cols-3"><MetricCard detail="全部任务完成时刻" icon={<Activity />} label="Makespan" value={`${latestRun.makespan}`} /><MetricCard detail={methodLabels[latestRun.method]} icon={<Clock3 />} label="求解耗时" value={`${latestRun.wall_time_s}s`} /><MetricCard detail={latestRun.status} icon={<Cpu />} label="任务 / 节点" value={`${latestRun.n_tasks} / ${latestRun.n_nodes}`} /></div><div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.5fr)]"><Card><CardHeader><CardTitle>节点负载</CardTitle><CardDescription>按处理时长统计节点利用情况。</CardDescription></CardHeader><CardContent className="grid gap-4">{nodeLoads.map((node) => <div className="grid gap-2" key={node.nodeId}><div className="flex justify-between text-sm"><span>{latestRun.nodes[node.nodeId]?.name ?? `Node ${node.nodeId}`}</span><span className="text-muted-foreground">{node.taskCount} tasks · {node.totalDuration} time units</span></div><div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary" style={{ width: `${node.ratio}%` }} /></div></div>)}</CardContent></Card><TaskTable run={latestRun} /></div></> : <div className="border border-dashed p-10 text-center text-muted-foreground">导入任务数据或直接运行一次调度，这里会显示指标、负载和任务分配。</div>}
    <HistoryPanel query={historyQuery} />
  </div>
}

function NumberField({ label, min, max, value, onChange }: { label: string; min: number; max?: number; value: number; onChange: (value: number) => void }) { return <label className="grid gap-2 text-sm font-medium">{label}<Input max={max} min={min} onChange={(event) => onChange(Number(event.target.value))} type="number" value={value} /></label> }
function ComparisonPanel({ runs }: { runs: SchedulingRun[] }) { const bestMakespan = Math.min(...runs.map((run) => run.makespan)); return <Card><CardHeader><CardTitle>算法对比</CardTitle><CardDescription>所有算法基于同一任务实例运行，最小 makespan 标记为最优。</CardDescription></CardHeader><CardContent><div className="grid gap-3 md:grid-cols-4">{runs.map((run) => <div className={`rounded-lg border p-4 ${run.makespan === bestMakespan ? "border-primary bg-primary/5" : ""}`} key={run.id}><div className="flex items-center justify-between gap-2"><span className="font-medium">{methodLabels[run.method]}</span>{run.makespan === bestMakespan ? <Badge>最优</Badge> : null}</div><p className="mt-3 text-2xl font-semibold">{run.makespan}</p><p className="text-xs text-muted-foreground">Makespan · {run.wall_time_s}s</p></div>)}</div><Table><TableHeader><TableRow><TableHead>算法</TableHead><TableHead>Makespan</TableHead><TableHead>耗时</TableHead><TableHead>规模</TableHead><TableHead>数据来源</TableHead></TableRow></TableHeader><TableBody>{runs.map((run) => <TableRow key={`comparison-${run.id}`}><TableCell>{methodLabels[run.method]}</TableCell><TableCell>{run.makespan}</TableCell><TableCell>{run.wall_time_s}s</TableCell><TableCell>{run.n_tasks} × {run.n_nodes}</TableCell><TableCell>{run.source_name}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card> }
function TaskTable({ run }: { run: SchedulingRun }) { return <Card><CardHeader><CardTitle>任务分配</CardTitle><CardDescription>包含数据量、优先级、截止时间和节点分配。</CardDescription></CardHeader><CardContent><Table><TableHeader><TableRow><TableHead>任务</TableHead><TableHead>节点</TableHead><TableHead>优先级</TableHead><TableHead>数据量</TableHead><TableHead>开始</TableHead><TableHead>持续</TableHead><TableHead>截止</TableHead><TableHead>完成</TableHead></TableRow></TableHeader><TableBody>{run.tasks.map((task) => <TableRow key={task.task_id}><TableCell>Task {task.task_id}</TableCell><TableCell>{task.node_name}</TableCell><TableCell>{task.priority}</TableCell><TableCell>{task.data_size_mb} MB</TableCell><TableCell>{task.start_time}</TableCell><TableCell>{task.duration}</TableCell><TableCell>{task.deadline}</TableCell><TableCell>{task.end_time}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card> }
function HistoryPanel({ query }: { query: ReturnType<typeof useQuery> }) { const data = query.data as { data?: SchedulingRun[] } | undefined; return <Card><CardHeader><CardTitle>历史运行</CardTitle><CardDescription>仅显示当前账号提交的调度运行。</CardDescription></CardHeader><CardContent>{query.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : <Table><TableHeader><TableRow><TableHead>时间</TableHead><TableHead>方法</TableHead><TableHead>规模</TableHead><TableHead>Makespan</TableHead><TableHead>来源</TableHead><TableHead>状态</TableHead></TableRow></TableHeader><TableBody>{(data?.data ?? []).map((run) => <TableRow key={run.id}><TableCell>{run.created_at ? new Date(run.created_at).toLocaleString() : "-"}</TableCell><TableCell>{methodLabels[run.method]}</TableCell><TableCell>{run.n_tasks} × {run.n_nodes}</TableCell><TableCell>{run.makespan}</TableCell><TableCell>{run.source_name}</TableCell><TableCell><Badge variant="outline">{run.status}</Badge></TableCell></TableRow>)}</TableBody></Table>}</CardContent></Card> }
function MetricCard({ icon, label, value, detail }: { icon: ReactNode; label: string; value: string; detail: string }) { return <Card><CardContent className="flex items-start gap-3 pt-6"><div className="rounded-md bg-primary/10 p-2 text-primary">{icon}</div><div className="min-w-0"><p className="text-sm text-muted-foreground">{label}</p><p className="text-2xl font-semibold">{value}</p><p className="truncate text-xs text-muted-foreground">{detail}</p></div></CardContent></Card> }

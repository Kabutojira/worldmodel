import { loadQuartzConfig, loadQuartzLayout } from "./quartz/plugins/loader/config-loader"
import worldmodelLayout from "./quartz.layout"

const config = await loadQuartzConfig()
export default config
export const worldmodelQuartzLayout = worldmodelLayout
export const layout = await loadQuartzLayout()

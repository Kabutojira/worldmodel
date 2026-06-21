export type WorldModelQuartzLayout = {
  mobile: {
    sidebar: string
    graph: string
    search: string
  }
  graph: {
    plugin: string
    placement: string
    rationale: string
  }
  content: {
    sourceOfTruth: string
    generatedContent: string
  }
}

const layout: WorldModelQuartzLayout = {
  mobile: {
    sidebar: "Explorer and toolbar remain on the left rail; Quartz collapses them responsively on smaller screens.",
    graph: "Local/global graph stays in the right rail on desktop and naturally drops below article content on tablet/mobile.",
    search: "Search remains in the toolbar group so it stays accessible on phones without dominating the viewport.",
  },
  graph: {
    plugin: "github:quartz-community/graph",
    placement: "Right sidebar for local graph with global graph toggle enabled.",
    rationale: "Graph density is reduced for mobile by smaller scale, link distance, and font size while keeping drag and zoom enabled.",
  },
  content: {
    sourceOfTruth: "Repository Markdown and CSV files remain canonical.",
    generatedContent: "site/content and site/public are generated artifacts and must not be edited manually.",
  },
}

export default layout

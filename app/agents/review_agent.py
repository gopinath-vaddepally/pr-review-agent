"""
Review Agent component.

LangGraph-orchestrated autonomous agent that analyzes a single pull request.
Implements a state graph with nodes for each phase of the review process.
"""

import time
from typing import Dict, Any, TypedDict, List
from langgraph.graph import StateGraph, END

from app.models.agent import AgentState, AgentStatus
from app.models.comment import LineComment, SummaryComment
from app.models.file_change import FileChange
from app.models.ast_node import ASTNode
from app.models.pr_event import PRMetadata
from app.services.code_retriever import CodeRetriever
from app.services.redis_client import RedisClient
from app.analyzers.code_analyzer import CodeAnalyzer
from app.analyzers.architecture_analyzer import ArchitectureAnalyzer
from app.services.comment_publisher import CommentPublisher
from plugins.manager import PluginManager
from app.utils.logging import get_logger, log_phase_transition
from app.utils.metrics import MetricsCollector

logger = get_logger(__name__)


class ReviewAgentState(TypedDict):
    """State schema for Review Agent."""
    agent_id: str
    pr_id: str
    pr_metadata: PRMetadata
    repository_id: str
    changed_files: List[FileChange]
    parsed_asts: Dict[str, ASTNode]
    line_comments: List[LineComment]
    summary_comment: SummaryComment | None
    errors: List[str]
    phase: str
    start_time: float
    end_time: float | None


class ReviewAgent:
    """Autonomous agent for analyzing pull requests using LangGraph."""
    
    def __init__(
        self,
        agent_id: str,
        pr_metadata: PRMetadata,
        repository_id: str
    ):
        """
        Initialize Review Agent.
        
        Args:
            agent_id: Unique agent identifier
            pr_metadata: Pull request metadata
            repository_id: Repository identifier
        """
        self.agent_id = agent_id
        self.pr_metadata = pr_metadata
        self.repository_id = repository_id
        
        # Initialize services
        self.redis_client = RedisClient()
        self.code_retriever = CodeRetriever()
        self.plugin_manager = PluginManager()
        self.code_analyzer = CodeAnalyzer(self.plugin_manager)
        self.architecture_analyzer = ArchitectureAnalyzer()
        self.comment_publisher = CommentPublisher()
        
        # Initialize metrics collector
        self.metrics = MetricsCollector(agent_id, pr_metadata.pr_id, repository_id)
        
        # Build state graph
        self.graph = self._build_state_graph()
    
    def _build_state_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph for the review workflow.
        
        Returns:
            Configured StateGraph
        """
        workflow = StateGraph(ReviewAgentState)
        
        # Add nodes
        workflow.add_node("initialize", self._initialize_node)
        workflow.add_node("retrieve_code", self._retrieve_code_node)
        workflow.add_node("parse_files", self._parse_files_node)
        workflow.add_node("line_analysis", self._line_analysis_node)
        workflow.add_node("architecture_analysis", self._architecture_analysis_node)
        workflow.add_node("generate_comments", self._generate_comments_node)
        workflow.add_node("publish_comments", self._publish_comments_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Define edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "retrieve_code")
        workflow.add_edge("retrieve_code", "parse_files")
        workflow.add_edge("parse_files", "line_analysis")
        workflow.add_edge("line_analysis", "architecture_analysis")
        workflow.add_edge("architecture_analysis", "generate_comments")
        workflow.add_edge("generate_comments", "publish_comments")
        workflow.add_edge("publish_comments", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def execute(self) -> AgentState:
        """
        Execute the review agent workflow.
        
        Returns:
            Final agent state
        """
        logger.info(f"Starting Review Agent {self.agent_id} for PR {self.pr_metadata.pr_id}")
        
        # Start metrics collection
        self.metrics.start()
        
        # Initialize state
        initial_state: ReviewAgentState = {
            "agent_id": self.agent_id,
            "pr_id": self.pr_metadata.pr_id,
            "pr_metadata": self.pr_metadata,
            "repository_id": self.repository_id,
            "changed_files": [],
            "parsed_asts": {},
            "line_comments": [],
            "summary_comment": None,
            "errors": [],
            "phase": "initialize",
            "start_time": time.time(),
            "end_time": None
        }
        
        try:
            # Execute graph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Convert to AgentState model
            agent_state = AgentState(
                agent_id=final_state["agent_id"],
                pr_id=final_state["pr_id"],
                pr_metadata=final_state["pr_metadata"],
                phase=final_state["phase"],
                start_time=final_state["start_time"],
                end_time=final_state.get("end_time"),
                changed_files=final_state["changed_files"],
                parsed_asts=final_state["parsed_asts"],
                line_comments=final_state["line_comments"],
                summary_comment=final_state.get("summary_comment"),
                errors=final_state["errors"]
            )
            
            logger.info(f"Review Agent {self.agent_id} completed successfully")
            return agent_state
            
        except Exception as e:
            logger.error(f"Review Agent {self.agent_id} failed: {e}", exc_info=True)
            
            # Complete metrics with error
            self.metrics.complete(status="failed", error_message=str(e))
            
            # Return error state
            return AgentState(
                agent_id=self.agent_id,
                pr_id=self.pr_metadata.pr_id,
                pr_metadata=self.pr_metadata,
                phase="failed",
                start_time=initial_state["start_time"],
                end_time=time.time(),
                changed_files=[],
                parsed_asts={},
                line_comments=[],
                summary_comment=None,
                errors=[str(e)]
            )
    
    async def _initialize_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Initialize node: Load PR metadata and validate inputs.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "initialize", "started")
        state["phase"] = "initialize"
        
        try:
            # Initialize plugin manager
            await self.plugin_manager.initialize_plugins()
            
            # Persist state
            await self._persist_state(state)
            
            log_phase_transition(logger, state['agent_id'], state['pr_id'], "initialize", "completed")
            
        except Exception as e:
            logger.error(f"[{state['agent_id']}] Initialization failed: {e}", exc_info=True)
            state["errors"].append(f"Initialization error: {str(e)}")
        
        return state
    
    async def _retrieve_code_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Retrieve code node: Fetch file diffs using Code Retriever.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "retrieve_code", "started")
        state["phase"] = "retrieve_code"
        
        try:
            # Get PR diff
            changed_files = await self.code_retriever.get_pr_diff(state["pr_id"])
            state["changed_files"] = changed_files
            
            self.metrics.record_files_analyzed(len(changed_files))
            logger.info(f"[{state['agent_id']}] Retrieved {len(changed_files)} changed files")
            
            # Persist state
            await self._persist_state(state)
            
            log_phase_transition(logger, state['agent_id'], state['pr_id'], "retrieve_code", "completed")
            
        except Exception as e:
            logger.error(f"[{state['agent_id']}] Code retrieval failed: {e}", exc_info=True)
            state["errors"].append(f"Code retrieval error: {str(e)}")
        
        return state
    
    async def _parse_files_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Parse files node: Parse changed files using language plugins.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "parse_files", "started")
        state["phase"] = "parse_files"
        
        parsed_asts = {}
        
        for file_change in state["changed_files"]:
            try:
                # Get plugin for file
                plugin = self.plugin_manager.get_plugin_for_file(file_change.file_path)
                
                if plugin and file_change.target_content:
                    # Parse file
                    ast = await plugin.parse_file(
                        file_change.file_path,
                        file_change.target_content
                    )
                    parsed_asts[file_change.file_path] = ast
                    logger.debug(f"[{state['agent_id']}] Parsed {file_change.file_path}")
                else:
                    logger.debug(f"[{state['agent_id']}] Skipping {file_change.file_path} (no plugin or content)")
                    
            except Exception as e:
                logger.warning(f"[{state['agent_id']}] Failed to parse {file_change.file_path}: {e}")
                state["errors"].append(f"Parse error for {file_change.file_path}: {str(e)}")
        
        state["parsed_asts"] = parsed_asts
        logger.info(f"[{state['agent_id']}] Parsed {len(parsed_asts)} files")
        
        # Persist state
        await self._persist_state(state)
        
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "parse_files", "completed")
        
        return state
    
    async def _line_analysis_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Line analysis node: Analyze each line using Code Analyzer.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "line_analysis", "started")
        state["phase"] = "line_analysis"
        
        all_comments = []
        
        for file_change in state["changed_files"]:
            try:
                # Get AST if available
                ast = state["parsed_asts"].get(file_change.file_path)
                
                if ast:
                    # Analyze file
                    comments = await self.code_analyzer.analyze_file(file_change, ast)
                    all_comments.extend(comments)
                    logger.debug(f"[{state['agent_id']}] Analyzed {file_change.file_path}: {len(comments)} comments")
                    
            except Exception as e:
                logger.warning(f"[{state['agent_id']}] Failed to analyze {file_change.file_path}: {e}")
                state["errors"].append(f"Analysis error for {file_change.file_path}: {str(e)}")
        
        state["line_comments"] = all_comments
        self.metrics.record_line_comments(len(all_comments))
        logger.info(f"[{state['agent_id']}] Generated {len(all_comments)} line comments")
        
        # Persist state
        await self._persist_state(state)
        
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "line_analysis", "completed")
        
        return state
    
    async def _architecture_analysis_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Architecture analysis node: Evaluate overall design using Architecture Analyzer.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "architecture_analysis", "started")
        state["phase"] = "architecture_analysis"
        
        try:
            # Analyze architecture
            summary_comment = await self.architecture_analyzer.analyze_architecture(
                state["changed_files"],
                state["parsed_asts"]
            )
            state["summary_comment"] = summary_comment
            self.metrics.record_summary_comment(summary_comment is not None)
            
            logger.info(f"[{state['agent_id']}] Architecture analysis complete")
            
        except Exception as e:
            logger.error(f"[{state['agent_id']}] Architecture analysis failed: {e}", exc_info=True)
            state["errors"].append(f"Architecture analysis error: {str(e)}")
        
        # Persist state
        await self._persist_state(state)
        
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "architecture_analysis", "completed")
        
        return state
    
    async def _generate_comments_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Generate comments node: Format analysis results as Azure DevOps comments.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        logger.info(f"[{state['agent_id']}] Phase: Generate Comments")
        state["phase"] = "generate_comments"
        
        # Comments are already generated in previous phases
        # This node is for any additional formatting or validation
        
        logger.info(f"[{state['agent_id']}] Ready to publish {len(state['line_comments'])} line comments "
                   f"and {'1 summary' if state['summary_comment'] else 'no summary'}")
        
        # Persist state
        await self._persist_state(state)
        
        return state
    
    async def _publish_comments_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Publish comments node: Post comments using Comment Publisher.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "publish_comments", "started")
        state["phase"] = "publish_comments"
        
        try:
            if state["line_comments"] or state["summary_comment"]:
                # Batch publish all comments
                result = await self.comment_publisher.batch_publish(
                    state["pr_id"],
                    state["repository_id"],
                    state["line_comments"],
                    state["summary_comment"] or SummaryComment(message="No architectural issues detected.")
                )
                
                if not result.success:
                    state["errors"].extend(result.errors)
                
                logger.info(f"[{state['agent_id']}] Published {result.published_count} comments, "
                           f"{result.failed_count} failed")
            else:
                logger.info(f"[{state['agent_id']}] No comments to publish")
            
        except Exception as e:
            logger.error(f"[{state['agent_id']}] Comment publishing failed: {e}", exc_info=True)
            state["errors"].append(f"Publishing error: {str(e)}")
        
        # Mark as complete
        state["phase"] = "complete"
        state["end_time"] = time.time()
        
        # Complete metrics collection
        status = "completed" if not state["errors"] else "failed"
        error_msg = "; ".join(state["errors"]) if state["errors"] else None
        self.metrics.complete(status=status, error_message=error_msg)
        
        # Persist final state
        await self._persist_state(state)
        
        log_phase_transition(logger, state['agent_id'], state['pr_id'], "publish_comments", "completed")
        
        return state
    
    async def _handle_error_node(self, state: ReviewAgentState) -> ReviewAgentState:
        """
        Handle error node: Log errors and determine recovery strategy.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state
        """
        logger.error(f"[{state['agent_id']}] Phase: Handle Error")
        state["phase"] = "error"
        state["end_time"] = time.time()
        
        # Log all errors
        for error in state["errors"]:
            logger.error(f"[{state['agent_id']}] Error: {error}")
        
        # Persist error state
        await self._persist_state(state)
        
        return state
    
    async def _persist_state(self, state: ReviewAgentState) -> None:
        """
        Persist agent state to Redis.
        
        Args:
            state: Current agent state
        """
        try:
            # Convert state to AgentState model for serialization
            agent_state = AgentState(
                agent_id=state["agent_id"],
                pr_id=state["pr_id"],
                pr_metadata=state["pr_metadata"],
                phase=state["phase"],
                start_time=state["start_time"],
                end_time=state.get("end_time"),
                changed_files=state["changed_files"],
                parsed_asts=state["parsed_asts"],
                line_comments=state["line_comments"],
                summary_comment=state.get("summary_comment"),
                errors=state["errors"]
            )
            
            # Save to Redis
            await self.redis_client.save_agent_state(state["agent_id"], agent_state)
            
        except Exception as e:
            logger.error(f"[{state['agent_id']}] Failed to persist state: {e}")

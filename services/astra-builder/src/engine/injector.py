from lxml import etree
import copy
from typing import List, Optional
from src.engine.xml_loader import XMLLoader

class ContentInjector:
    """
    Injects dynamic content into the XML tree while preserving original styles.
    """
    
    def __init__(self, loader: XMLLoader):
        self.loader = loader
        self.w_ns = self.loader.NAMESPACES['w']

    def inject_text(self, anchor_id: str, text: str, mode: str = "REPLACE"):
        """
        Injects text at the specified anchor ID.
        
        Args:
            anchor_id: The astra:id of the target node.
            text: The content to inject.
            mode: 'REPLACE' (clears existing text) or 'APPEND'.
        """
        target_node = self.loader.get_node_by_id(anchor_id)
        if target_node is None:
            print(f"[ContentInjector] Warning: Anchor {anchor_id} not found.")
            return

        # 1. Identify Parent Paragraph (w:p) or Run (w:r)
        # We need to find the run level to clone properties (w:rPr)
        # Assuming anchor is on a run or paragraph
        
        # If anchor is paragraph, we look for runs inside
        # If anchor is run, we use it directly
        
        if target_node.tag.endswith(f"{{{self.w_ns}}}p"):
            self._inject_into_paragraph(target_node, text, mode)
        elif target_node.tag.endswith(f"{{{self.w_ns}}}r"):
            self._inject_into_run(target_node, text, mode)
        else:
             print(f"[ContentInjector] Warning: Unsupported node type {target_node.tag}")

    def _inject_into_paragraph(self, p_node: etree._Element, text: str, mode: str):
        """
        Injects content into a paragraph, ensuring style consistency.
        Uses the first run's properties as a template for new content.
        """
        # Find first run to use as style template
        template_run = p_node.find(f"{{{self.w_ns}}}r")
        
        if mode == "REPLACE":
            # Clear all existing runs but keep pPr
            for child in list(p_node):
                if child.tag.endswith(f"{{{self.w_ns}}}r"):
                    p_node.remove(child)
        
        # Create new run
        new_run = etree.SubElement(p_node, f"{{{self.w_ns}}}r")
        
        # Graft Style from template if available
        if template_run is not None:
            rPr = template_run.find(f"{{{self.w_ns}}}rPr")
            if rPr is not None:
                new_run.append(copy.deepcopy(rPr))
        
        # Add Text
        t_node = etree.SubElement(new_run, f"{{{self.w_ns}}}t")
        t_node.text = text

    def _inject_into_run(self, r_node: etree._Element, text: str, mode: str):
        """
        Injects content into a specific run.
        """
        t_node = r_node.find(f"{{{self.w_ns}}}t")
        
        if t_node is None:
             t_node = etree.SubElement(r_node, f"{{{self.w_ns}}}t")
        
        if mode == "REPLACE":
            t_node.text = text
        else:
            t_node.text = (t_node.text or "") + text

    def inject_xml(self, anchor_id: str, raw_xml: str):
        """
        Injects a raw XML string (e.g., a w:p element) replacing the anchor node.
        """
        target_node = self.loader.get_node_by_id(anchor_id)
        if target_node is None:
            print(f"[ContentInjector] Warning: Anchor {anchor_id} not found.")
            return

        # 1. Parse the raw XML
        try:
            # We wrap in a dummy root ensures we can parse fragments with multiple siblings or just to be safe
            # But usually LLM generates a single <w:p>... </w:p>.
            # Let's try parsing directly. If it fails, might need wrapping.
            # We assume raw_xml is a valid XML fragment (e.g. <w:p>...</w:p>)
            
            # Important: lxml needs namespaces to be defined if they are used in the fragment
            # We can use the loader's map, but usually etree.fromstring might complain if prefixes aren't there.
            # A trick is to wrap it: <root xmlns:w="..."> {raw_xml} </root>
            
            namespace_declarations = ' '.join([f'xmlns:{k}="{v}"' for k, v in self.loader.NAMESPACES.items()])
            wrapped_xml = f'<root {namespace_declarations}>{raw_xml}</root>'
            
            dummy_root = etree.fromstring(wrapped_xml)
            new_nodes = list(dummy_root)
            
        except etree.XMLSyntaxError as e:
            print(f"[ContentInjector] Error parsing injected XML for {anchor_id}: {e}")
            return

        # 2. Insert new nodes after the target (anchor)
        parent = target_node.getparent()
        if parent is None:
             print(f"[ContentInjector] Error: Anchor {anchor_id} has no parent.")
             return
             
        # We insert the new nodes before the anchor, then remove the anchor? 
        # Or after? The implementation plan said "Insert new elements after the anchor".
        # But usually we want to REPLACE the anchor. 
        # So "Insert Before" + "Remove Anchor" is equivalent to "Replace".
        
        index = parent.index(target_node)
        for i, node in enumerate(new_nodes):
            parent.insert(index + i, node)
            
        # 3. Remove the anchor node
        parent.remove(target_node)


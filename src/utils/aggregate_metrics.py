#!/usr/bin/env python3
import json
import os
import glob
from collections import defaultdict
import numpy as np

def load_metrics_file(file_path):
    """Load a metrics JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def aggregate_metrics(files):
    """Aggregate metrics from multiple files."""
    total_examples = 0
    valid_examples = 0
    error_count = 0
    
    # For collecting all values to calculate overall statistics
    metrics_collector = defaultdict(list)
    all_results = []
    
    # Keep track of model paths
    model_paths = set()
    
    for file_path in files:
        try:
            data = load_metrics_file(file_path)
            
            # Accumulate counts
            summary = data.get("summary", {})
            total_examples += summary.get("total_examples", 0)
            valid_examples += summary.get("valid_examples", 0)
            error_count += summary.get("error_count", 0)
            
            # Keep track of model paths
            if "model_path" in summary:
                model_paths.add(summary["model_path"])
            
            # Collect all metric values
            metrics = summary.get("metrics", {})
            for metric_name, metric_value in metrics.items():
                if metric_name.startswith("avg_") or metric_name.startswith("median_"):
                    # For averages and medians, we need the raw values
                    continue
                metrics_collector[metric_name].append(metric_value)
            
            # Combine results arrays
            if "results" in data:
                all_results.extend(data["results"])
                
            # Collect raw values for recalculating averages/medians
            if "results" in data:
                for result in data["results"]:
                    for key, value in result.items():
                        if key in ["bleu_1", "bleu_2", "bleu_4", 
                                  "rouge1_fmeasure", "rouge2_fmeasure", 
                                  "rougeL_fmeasure", "levenshtein_similarity",
                                  "execution_time"]:
                            metrics_collector[key].append(value)
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    # Calculate aggregate metrics
    aggregate_metrics = {}
    for metric_name, values in metrics_collector.items():
        if len(values) > 0:
            # Raw metrics (not avg/min/max/median prefixed)
            if not any(metric_name.startswith(prefix) for prefix in ["avg_", "min_", "max_", "median_"]):
                # Calculate statistics
                try:
                    aggregate_metrics[f"avg_{metric_name}"] = np.mean(values)
                    aggregate_metrics[f"min_{metric_name}"] = np.min(values) 
                    aggregate_metrics[f"max_{metric_name}"] = np.max(values)
                    aggregate_metrics[f"median_{metric_name}"] = np.median(values)
                except Exception as e:
                    print(f"Error calculating stats for {metric_name}: {e}")
    
    # Create aggregate summary
    aggregate_summary = {
        "total_examples": total_examples,
        "valid_examples": valid_examples,
        "error_count": error_count,
        "error_rate": error_count / total_examples if total_examples > 0 else 0,
        "with_context": summary.get("with_context", None),
        "model_paths": list(model_paths),
        "metrics": aggregate_metrics
    }
    
    return {
        "summary": aggregate_summary,
        "results": all_results
    }

def main():
    # Find all metric files
    metric_files = glob.glob("results/metrics/wcontext/*_res_*.json")
    if not metric_files:
        print("No metric files found!")
        return
    
    print(f"Found {len(metric_files)} metric files to aggregate.")
    
    # Aggregate metrics
    aggregated_data = aggregate_metrics(metric_files)
    
    # Save the aggregated data
    output_path = "results/metrics/wcontext/total_metrics.json"
    with open(output_path, 'w') as f:
        json.dump(aggregated_data, f, indent=2)
    
    print(f"Aggregated metrics saved to {output_path}")
    print(f"Total examples: {aggregated_data['summary']['total_examples']}")
    print(f"Valid examples: {aggregated_data['summary']['valid_examples']}")

if __name__ == "__main__":
    main()

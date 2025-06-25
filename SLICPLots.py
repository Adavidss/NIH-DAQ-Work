import matplotlib.pyplot as plt
import numpy as np

def plot_xy(x_data, y_data, title="X vs Y Plot", xlabel="X", ylabel="Y", 
            color='blue', style='-', marker='o', figsize=(6,4)):
    
    # Create figure and axis objects with specific size
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot data with specified style
    ax.plot(x_data, y_data, color=color, linestyle=style, 
            marker=marker, label='Data')
    
    # Customize plot
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    return fig, ax

# Example usage
if __name__ == "__main__":
    # TimeSLIC_approx data (variable changed) (date:6/5/2025)
    x1 = [.126,.120,.142,0.0335,0.0445,0.0471,0.0874,0.0921,0.0913,0.0819,0.0770,0.0673,0.0837,0.0870]
    y1 = [50,50,50,10,70,70,100,100,150,40,30,60,50]
    
    # 40 sec TimeSLIC_approx and same parameters outside of others
    # Change B1_SLIC (date:6/5/2025)
    x2 = [0.0819,0.0374,0.151,0.141,0.136,0.108,.110,.120,0.0670,0.111,0.129,0.154]
    y2 = [1.8,1,3,5,3.5,2.5,3,3,2,3,3.2,4]
    
    # 40 sec TimeSLIC_approx and same parameters outside of others
    # Change B1_SLIC (date:6/6/2025)
    x3 = [0.153,0.157,.101,0.101,0.115,.168,.181,.209,0.211,0.223,0.210,0.215,0.220,0.226,0.231,.262,0.231,0.230,0.231,0.233,0.235,0.250]
    y3 = [1.8,1.9,2.0,2.0,2.1,2.2,2.3,2.4,2.5,2.5,2.6,2.7,2.8,2.9,3.0,3.1,3.1,3.1,3.2,3.3,3.5,4.0]

    # 40 sec TimeSLIC_approx, 4.0 uT B1_SLIC, and same parameters outside of others
    # Change f_SLIC (date:6/6/2025)
    x4 = [0.237, 0.223, 0.08515, 0.0433, 0.0333, 0.00725, 0.01459, 0.00213, 0, 0, 0.38, 0.397, 0.398, 0.359, 0.359, 0.406, 0.359, 0.41, 0.415, 0.3984, 0.363, 0.394, 0.373, 0.344, 0.3605, 0.342, 0.286, 0.263, 0.186, 0.399, 0.3775, 0.22, 0.305]
    y4 = [535.25, 545, 525, 555, 515, 565, 505, 575, 585, 495, 535.25, 535.25, 535.25, 535.25, 535, 534, 536, 533, 537, 537, 537, 538, 539, 540, 541, 542, 543, 544, 545, 535, 534, 533, 532]
    
    # off resonant, then back to on resonant. Putting back on resonance (535.25Hz) getting much better signal than before

    # Sort x1-y1 pairs by y1 values in ascending order
    xy1_pairs = list(zip(x1[:-1], y1))  # Remove extra x1 value to match y1 length
    xy1_pairs.sort(key=lambda pair: pair[1])
    x1, y1 = zip(*xy1_pairs)
    x1, y1 = list(x1), list(y1)
    
    # Create plot
    fig, ax = plot_xy(y3, x3, 
                      title="SLIC Plot Undeuterated", 
                      xlabel="B1_SLIC (uT)", 
                      ylabel="Amplitude",
                      color='red',
                      style='-')
    
    plt.show()


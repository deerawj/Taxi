function toggleAvailability() {
    // Implement logic to toggle driver availability (Ajax request to server, for example)
    const statusElement = document.getElementById('status');
    const currentStatus = statusElement.innerText;
  
    if (currentStatus === 'AVAILABLE') {
      // Change status to BUSY when becoming unavailable
      statusElement.innerText = 'BUSY';
    } else {
      // Change status to AVAILABLE when becoming available
      statusElement.innerText = 'AVAILABLE';
    }
  
    // Additional logic to update server-side status
    // (e.g., send an Ajax request to the server to update the driver's status)
  }
  
    
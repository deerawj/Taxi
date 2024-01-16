document.addEventListener('DOMContentLoaded', function () {
    const carousel = document.getElementById('myCarousel');
    let currentIndex = 0;
  
   
    function toggleItems(index) {
      const items = carousel.getElementsByClassName('carousel-item');
      for (let i = 0; i < items.length; i++) {
        items[i].style.display = i === index ? 'block' : 'none';
      }
    }
  
    
    function handleCarouselClick() {
      currentIndex = (currentIndex + 1) % 2; 
      toggleItems(currentIndex);
    }
  
    
    carousel.addEventListener('click', handleCarouselClick);
  });
  
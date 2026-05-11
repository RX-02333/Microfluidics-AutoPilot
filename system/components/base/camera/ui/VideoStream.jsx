import React from 'react';

const VideoStream = ({ src, style, title = "Video Stream" }) => {
    return (
        <iframe
            src={src}
            style={{ width: '100%', height: '100%', border: 'none', ...style }}
            title={title}
        />
    );
};

export default VideoStream;

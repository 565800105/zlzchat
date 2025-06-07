/**
 * 图片上传组件，支持拖拽排序
 * Copyright (c) 2024 smanor
 */
Vue.component('vuedraggable', window.vuedraggable);
Vue.component('images-upload', {
    template: `<div class="jd-images-upload">
                 <draggable v-model="fileList" @input="syncData" class="el-upload-list el-upload-list--picture-card" style="float: left">
                     <div v-for="(item, index) in fileList" :key="index" class="el-upload-list__item is-success animated">
                         <div v-if="getType(item.url) == 'image'" :style="setBg(item.url)"></div>
                         <video v-if="getType(item.url) == 'video'" style="width: 100%; height: 100% !important; object-fit: cover"><source :src="item.url" type="video/mp4" /></video>
                         <span class="el-upload-list__item-actions">
                             <span class="el-upload-list__item-preview" title="查看" @click="openDetail(item)">
                               <i class="el-icon-zoom-in"></i>
                             </span>
                             <span class="el-upload-list__item-delete" title="删除" @click="remove(index)">
                               <i class="el-icon-delete"></i>
                             </span>
                         </span>
                     </div>
                 </draggable>
                 <el-upload
                     action="/admin/common/upload"
                     list-type="picture-card"
                     class="avatar-uploader"
                     :multiple="maxnumber > 1"
                     :limit="maxnumber"
                     :accept="accepttype.join(',')"                     
                     :file-list="fileList"
                     :show-file-list="false"
                     :on-exceed="exceedLimit"
                     :before-upload="uploadBeforeCheck"
                     :on-success="uploadSuccess"
                 >
                     <i class="el-icon-plus"></i>
                 </el-upload>
                 <el-dialog v-if="showDetail" :visible.sync="showDetail" append-to-body>
                    <div style="display: flex; justify-content: center; align-items: center">
                        <img v-if="getType(detailUrl) == 'image'" :src="detailUrl" style="max-width: 100%; height: auto;" />
                        <video v-if="getType(detailUrl) == 'video'" controls autoplay><source :src="detailUrl" type="video/mp4" /></video>
                    </div>     
                 </el-dialog>
            </div>`,
    props: {
        //原始（已上传）文件
        datalist: {
            type: Array | String
        },
        //允许上传类型
        accepttype: {
            type: Array,
            default: () => ['image/jpg', 'image/jpeg', 'image/png', 'image/gif', 'image/tiff', 'audio/mp4', 'video/mp4']
        },
        //最大文件质量大小（MB)
        maxsize: {
            type: Number,
            default: 2
        },
        //最大文件数量
        maxnumber: {
            type: Number,
            default: 1
        }
    },
    data() {
        return {
            fileList: [],
            showDetail: false,
            detailUrl: '',
        }
    },
    created() {
        if(typeof this.datalist === 'string' && this.datalist && this.datalist.length > 0){
            this.datalist.split(',').forEach((item, index) =>
                this.fileList.push({id: index, name: item, url: item})
            );
        }else if(typeof this.datalist === 'object' && this.datalist != null && this.datalist.length > 0){
            this.datalist.forEach(item => {
                this.fileList.push({id:item.id, name: item.name, url: item.url});
            });
        }
    },
    mounted(){},
    methods: {
        exceedLimit(files, fileList){
            this.$message.error('文件数量不能超过 ' + this.maxnumber + '个');
        },
        uploadBeforeCheck(file){
            let type = file.type.toLowerCase(), size = file.size / 1024 / 1024;
            if(!this.accepttype.some(item => item == type)){
                let accepttypes = [];
                this.accepttype.forEach(item => accepttypes.push(item.split('/')[1]))
                this.$message.error('文件类型错误，只允许：' + accepttypes.join(','));
                return false;
            }
            if(this.maxsize < size){
                this.$message.error('文件大小不能超过 ' + this.maxsize + 'MB');
                return false;
            }
            return true;
        },
        uploadSuccess(res, file, fileList){
            if(res.code === 0){
                this.fileList.push({id: parseInt(Math.random() * 10000), name: res.originalFilename, url: res.fileName});
                this.syncData();
            }
        },
        getType(fileName) {
            let suffix = '', result = '', videoTypes = ['mp4', 'm2v', 'mkv'];
            try {
                let flieArr = fileName.split('.');
                suffix = flieArr[flieArr.length - 1].toLowerCase();
            } catch (err) {
                suffix = '';
            }
            if (suffix && suffix.length > 0) {
                let isVideo = videoTypes.some(item => item == suffix);
                result = isVideo ? 'video' : 'image';
            }
            return result;
        },
        setBg(url){
            return {
                backgroundImage: 'url(' + url + ')',
                backgroundRepeat: 'no-repeat',
                backgroundSize: 'cover',
                backgroundPosition: 'center center',
                width: '100%',
                height: '100%'
            }
        },
        openDetail(file) {
            this.detailUrl = file.url;
            this.showDetail = true;
        },
        remove(index){
            this.fileList.splice(index, 1);
            this.syncData();
        },
        syncData(){
            if(typeof this.datalist === 'string'){
                this.$emit('update:datalist', this.fileList.map(item => item.url).join(","));
            }else if(typeof this.datalist === 'object'){
                this.$emit('update:datalist', this.fileList);
            }
        }
    }
});